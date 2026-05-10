import sys
sys.path.insert(0, 'src')
from webqa.pipeline import WebsiteQAPipeline

# Initialize pipeline
pipeline = WebsiteQAPipeline()
pipeline._ensure_retriever()

# Test question about prayer
question = "ماهو حكم ترك الصلاة"
print(f"Question: {question}\n")

# Get retrieval results
results = pipeline.retriever.retrieve(question, top_k=4)
print(f"=== Top {len(results)} Retrieved Chunks ===\n")
for i, result in enumerate(results, 1):
    print(f"Result {i}:")
    print(f"  Score: {result.score:.4f}")
    print(f"  URL: {result.chunk.url}")
    print(f"  Title: {result.chunk.title}")
    print(f"  Text preview: {result.chunk.text[:150]}...")
    print()

# Try QA
print("=== QA Response ===\n")
answer = pipeline.ask(question)
print(f"Answer: {answer.answer}")
print(f"Confidence: {answer.confidence}")
if answer.sources:
    print(f"Sources: {len(answer.sources)} document(s)")
    for src in answer.sources[:2]:
        print(f"  - {src}")
