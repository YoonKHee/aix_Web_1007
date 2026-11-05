자유게시판 (board 앱)

[켜기]
1) project01/settings.py  INSTALLED_APPS 에  'board',  추가
2) project01/urls.py      urlpatterns 에  path('board/', include('board.urls')),  추가
3) python manage.py makemigrations board
   python manage.py migrate
4) 접속: http://127.0.0.1:8000/board/

[나중에 메인 화면에 붙이기 - 메인 index.html 에서]
링크만:      <a href="{% url 'board:list' %}">자유게시판</a>
최신글 박스: {% load board_tags %}  ...  {% latest_posts 5 %}

[관리]
- /admin/ 에서 글·댓글 숨김/복구, 금칙어·허용어 추가 (금칙어 추가 시 기존 글도 자동 검사)
- python manage.py scan_board   : 기존 글·댓글 금칙어 일괄 검사 (자동 숨김)
- 신고: 서로 다른 회원 3명이 신고하면 자동 숨김 (board/views.py REPORT_LIMIT)

[경기 예측 글 자동 작성]
- 경기 등록: /admin/ > 자유게시판 > Matches 에서 추가, 또는 CSV 로 한꺼번에
    python manage.py import_matches 일정.csv      (한 줄: 2026-11-01 14:00,울산HD,전북현대)
- 경기 시작 2일 전부터, 게시판 목록을 여는 순간 "AI 해설위원"이 글을 자동으로 올림 (경기당 1개)
- 수동 실행: python manage.py post_match_threads [--days 2]
