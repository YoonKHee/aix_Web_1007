import json
from datetime import datetime
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse, JsonResponse
from .models import ExamEvent

def index_view(request):
    return render(request, 'calendar_app/index.html')

def api_events_view(request):
    """모든 일정 데이터를 JSON으로 반환 (프론트엔드 렌더링용)"""
    events = ExamEvent.objects.all().values(
        'event_id', 'source', 'institution', 'title', 'event_type', 
        'start_date', 'end_date', 'official_url'
    )
    # 날짜 객체를 문자열로 변환
    event_list = []
    for ev in events:
        ev['start_date'] = ev['start_date'].strftime('%Y-%m-%d')
        ev['end_date'] = ev['end_date'].strftime('%Y-%m-%d')
        event_list.append(ev)
    return JsonResponse(event_list, safe=False)

def export_ics_view(request, event_id):
    """RFC 5545 표준 ICS 파일 다운로드"""
    event = get_object_or_404(ExamEvent, pk=event_id)
    
    dtstart = event.start_date.strftime('%Y%m%d')
    dtend = event.end_date.strftime('%Y%m%d')
    timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//ExaCal//Exam Calendar System//KO
BEGIN:VEVENT
UID:{event.event_id}@exacal.local
DTSTAMP:{timestamp}
DTSTART;VALUE=DATE:{dtstart}
DTEND;VALUE=DATE:{dtend}
SUMMARY:{event.title} ({event.event_type})
DESCRIPTION:주관기관: {event.institution}\\n공식링크: {event.official_url}
URL:{event.official_url}
END:VEVENT
END:VCALENDAR"""

    response = HttpResponse(ics_content, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{event.event_id}.ics"'
    return response