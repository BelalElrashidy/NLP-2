import os
import time

from dotenv import load_dotenv
from google.api_core.exceptions import GoogleAPICallError, ResourceExhausted
from google import generativeai as genai
from transformers import pipeline


class ExtractiveQA:
    def __init__(self, model_name: str) -> None:
        self.qa = pipeline("question-answering", model=model_name, tokenizer=model_name)

    def answer(self, question: str, contexts: list[str]) -> tuple[str, float]:
        """Run extractive QA per-chunk and pick the best answer.

        The per-chunk approach avoids silent truncation that happens when
        all chunks are concatenated into a single string that exceeds the
        model's 512-token limit.
        """
        best_answer = ""
        best_score = 0.0

        for ctx in contexts:
            ctx = ctx.strip()
            if not ctx:
                continue
            try:
                result = self.qa(question=question, context=ctx)
            except Exception:
                continue

            cand = str(result.get("answer", "")).strip()
            score = float(result.get("score", 0.0))

            # Prefer longer, higher-scoring answers
            if not cand or len(cand) < 2:
                continue
            if score > best_score or (
                abs(score - best_score) < 0.05 and len(cand) > len(best_answer)
            ):
                best_score = score
                best_answer = cand

        if not best_answer or len(best_answer) < 3:
            return "Answer not found in provided website content.", 0.0

        return best_answer, best_score


class GenerativeQA:
    def __init__(self, model_name: str) -> None:
        self.local_generator = None
        self.enable_local_fallback = os.getenv("WEBQA_ENABLE_LOCAL_FALLBACK", "false").lower() == "true"

        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            self.model = None
            return

        genai.configure(api_key=api_key)
        resolved_model = self._resolve_model_name(model_name)
        self.model = genai.GenerativeModel(model_name=resolved_model)

    @staticmethod
    def _resolve_model_name(requested_model: str) -> str:
        requested = requested_model if requested_model.startswith("models/") else f"models/{requested_model}"

        available = []
        for model in genai.list_models():
            methods = getattr(model, "supported_generation_methods", [])
            if "generateContent" in methods:
                available.append(model.name)

        if requested in available:
            return requested

        preferred = [
            "models/gemini-2.5-flash",
            "models/gemini-2.5-flash-lite",
            "models/gemini-2.5-flash-pro",
        ]
        for name in preferred:
            if name in available:
                return name

        for name in available:
            if "gemini" in name:
                return name

        raise ValueError("No Gemini model with generateContent support was found for this API key.")

    def answer(self, question: str, contexts: list[str]) -> str:
        # Use up to 6 context chunks for broader coverage
        numbered_contexts = []
        for i, ctx in enumerate(contexts[:6], 1):
            numbered_contexts.append(f"[مصدر {i}]\n{ctx}")
        context = "\n\n---\n\n".join(numbered_contexts)

        prompt = (
            "أنت مساعد متخصص في الإجابة على الأسئلة الشرعية والدينية بناءً على المحتوى المقدم فقط.\n"
            "التعليمات:\n"
            "- أجب باللغة العربية بشكل مفصل وشامل.\n"
            "- استخدم فقط المعلومات الموجودة في السياق أدناه.\n"
            "- اذكر الأدلة والآيات والأحاديث إن وُجدت في السياق.\n"
            "- إذا لم تجد الإجابة في السياق، قل: 'لم يتم العثور على إجابة في محتوى الموقع المقدم.'\n"
            "- لا تختلق معلومات غير موجودة في السياق.\n\n"
            f"السؤال: {question}\n\n"
            f"السياق:\n{context}\n\n"
            "الإجابة:"
        )
        if self.model is not None:
            retries = 3
            backoff_seconds = [5, 15, 30]
            for attempt in range(retries):
                try:
                    response = self.model.generate_content(prompt)
                    if response.text:
                        return response.text.strip()
                    break  # empty response, fall through
                except ResourceExhausted:
                    if attempt < retries - 1:
                        wait = backoff_seconds[attempt]
                        print(f"[GenerativeQA] Rate limited, retrying in {wait}s (attempt {attempt + 1}/{retries})...")
                        time.sleep(wait)
                        continue
                    if not self.enable_local_fallback:
                        raise RuntimeError(
                            "Gemini quota exhausted after retries. "
                            "Set WEBQA_ENABLE_LOCAL_FALLBACK=true to allow local fallback generation."
                        )
                except GoogleAPICallError:
                    if not self.enable_local_fallback:
                        raise RuntimeError(
                            "Gemini request failed (API error). "
                            "Set WEBQA_ENABLE_LOCAL_FALLBACK=true to allow local fallback generation."
                        )
                    break

        if not self.enable_local_fallback:
            if self.model is None:
                raise RuntimeError("GEMINI_API_KEY is missing. Add it in .env to run generative mode.")
            raise RuntimeError("Generative mode failed without fallback.")

        if self.local_generator is None:
            # Lightweight fallback model to avoid large downloads.
            self.local_generator = pipeline(
                "text2text-generation",
                model="google/flan-t5-small",
                tokenizer="google/flan-t5-small",
            )

        result = self.local_generator(prompt, max_new_tokens=256, do_sample=False)
        return str(result[0]["generated_text"]).strip()
