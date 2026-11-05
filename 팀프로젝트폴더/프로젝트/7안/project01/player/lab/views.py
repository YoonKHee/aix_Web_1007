"""감독 연구실 JSON API. 모두 POST(JSON) 이고 CSRF 토큰을 확인한다."""

import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from . import service


def _body(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        return {}


def _wrap(fn):
    @require_POST
    def view(request):
        try:
            return JsonResponse(fn(_body(request)), json_dumps_params={'ensure_ascii': False})
        except Exception as exc:                       # 화면이 멈추지 않도록 오류 문구만 돌려준다
            return JsonResponse({'error': f'계산 중 오류가 발생했습니다: {exc}'}, status=500,
                                json_dumps_params={'ensure_ascii': False})
    return view


lab_init = _wrap(service.api_init)
lab_lineup = _wrap(service.api_lineup)
lab_evaluate = _wrap(service.api_evaluate)
lab_candidates = _wrap(service.api_candidates)
lab_condition = _wrap(service.api_condition)
lab_schedule = _wrap(service.api_schedule)
lab_quality = _wrap(service.api_quality)
lab_formations = _wrap(service.api_formations)
lab_player_report = _wrap(service.api_player_report)
lab_chem_partners = _wrap(service.api_chem_partners)
