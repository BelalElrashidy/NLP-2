import json
import sys
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

from pathlib import Path

# Ensure repo src is on path
ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT.joinpath('src')
sys.path.insert(0, str(SRC))

from webqa.pipeline import WebsiteQAPipeline

# instantiate pipeline once
PIPELINE = WebsiteQAPipeline()


@csrf_exempt
def ask_view(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST required')

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return HttpResponseBadRequest('invalid json')

    prompt = payload.get('prompt')
    mode = payload.get('mode', 'generative')
    top_k = int(payload.get('top_k', 6))
    if not prompt:
        return HttpResponseBadRequest('prompt required')

    try:
        answer = PIPELINE.ask(question=prompt, mode=mode, top_k=top_k)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)

    return JsonResponse({
        'answer': answer.answer,
        'confidence': answer.confidence,
        'sources': [
            {'title': s.chunk.title, 'url': s.chunk.url, 'score': s.score} for s in answer.sources
        ],
    })
