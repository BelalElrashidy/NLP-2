import os

from dotenv import load_dotenv
from google.api_core.exceptions import GoogleAPICallError
from google import generativeai as genai
from transformers import pipeline


class ExtractiveQA:
    def __init__(self, model_name: str) -> None:
        self.qa = pipeline("question-answering", model=model_name, tokenizer=model_name)

    def answer(self, question: str, contexts: list[str]) -> tuple[str, float]:
        best_answer = ""
        best_score = 0.0

        for ctx in contexts:
            result = self.qa(question=question, context=ctx)
            score = float(result.get("score", 0.0))
            if score > best_score:
                best_score = score
                best_answer = str(result.get("answer", "")).strip()

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
            "models/gemini-2.0-flash",
            "models/gemini-1.5-flash",
            "models/gemini-1.5-flash-8b",
            "models/gemini-1.5-pro",
        ]
        for name in preferred:
            if name in available:
                return name

        for name in available:
            if "gemini" in name:
                return name

        raise ValueError("No Gemini model with generateContent support was found for this API key.")

    def answer(self, question: str, contexts: list[str]) -> str:
        context = "\n\n".join(contexts[:3])
        prompt = (
            "You are a factual website QA assistant. Use only the provided context. "
            "If the answer is missing, say: 'Answer not found in provided website content.'\n\n"
            f"Question: {question}\n\n"
            f"Context:\n{context}\n\n"
            "Answer:"
        )
        if self.model is not None:
            try:
                response = self.model.generate_content(prompt)
                if response.text:
                    return response.text.strip()
            except GoogleAPICallError:
                if not self.enable_local_fallback:
                    raise RuntimeError(
                        "Gemini request failed (likely quota/rate issue). "
                        "Set WEBQA_ENABLE_LOCAL_FALLBACK=true to allow local fallback generation."
                    )

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

        result = self.local_generator(prompt, max_new_tokens=140, do_sample=False)
        return str(result[0]["generated_text"]).strip()
