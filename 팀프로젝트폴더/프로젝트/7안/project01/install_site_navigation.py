"""공통 메뉴 설치.
manage.py가 있는 폴더에서 실행:
python install_site_navigation.py
"""

from datetime import datetime
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent


FILES = {
    'home/templates/shared/site_assets.html': r'''{% load static %}
<link rel="stylesheet" href="{% static 'home/site.css' %}">
<script src="{% static 'home/site_nav.js' %}" defer></script>
''',

    'home/templates/shared/site_header.html': r'''<a class="site-skip" href="#site-page-content">본문으로 건너뛰기</a>
<header class="site-header" data-site-header>
  <div class="site-inner">
    <a class="site-brand" href="/" aria-label="감독? 내가한다! 메인페이지">
      <span class="site-brand-icon" aria-hidden="true">⚽</span>
      <span>감독? 내가한다!<small>K LEAGUE MATCH STUDIO</small></span>
    </a>

    <button
      class="site-nav-toggle"
      type="button"
      aria-expanded="false"
      aria-controls="site-navigation"
      hidden
    >메뉴 열기 ☰</button>

    <div class="site-navigation" id="site-navigation">
      <nav class="site-links" aria-label="주요 메뉴">
        <a class="site-link" href="/"{% if active == 'home' %} aria-current="page"{% endif %}>메인</a>

        <a class="site-link site-best11"
           href="{% url 'player:best11' %}"
           {% if active == 'best11' %}aria-current="page"{% endif %}>🏆 BEST11</a>


        <a class="site-link"
           href="{% url 'player:plist' %}"
           {% if active == 'players' %}aria-current="page"{% endif %}>선수 기록</a>

        <a class="site-link site-predict"
           href="{% url 'team:simulate' %}"
           {% if active == 'predict' %}aria-current="page"{% endif %}>⚽ 승부예측</a>

        <a class="site-link"
           href="{% url 'board:list' %}"
           {% if active == 'board' %}aria-current="page"{% endif %}>자유게시판</a>
      </nav>

      <div class="site-account" aria-label="회원 메뉴">
        {% if user.is_authenticated %}
          <span class="site-user-name"
                title="{{ user.profile.nickname|default:user.get_username }}">{{ user.profile.nickname|default:user.get_username }}님</span>

          {% if user.is_superuser %}
            <a href="{% url 'manager:dashboard' %}">데이터 관리</a>
          {% elif user.is_staff %}
            <a href="/admin/board/">게시판 관리</a>
          {% endif %}

          <form class="site-logout"
                method="post"
                action="{% url 'board:logout' %}">
            {% csrf_token %}
            <button type="submit">로그아웃</button>
          </form>
        {% else %}
          <a href="{% url 'board:login' %}">로그인</a>
          <a href="{% url 'board:signup' %}">회원가입</a>
        {% endif %}
      </div>
    </div>
  </div>
</header>
<div id="site-page-content" tabindex="-1"></div>
''',

    'home/static/home/site_nav.js': r'''(() => {
    'use strict';

    const header = document.querySelector('[data-site-header]');
    if (!header) return;

    const toggle = header.querySelector('.site-nav-toggle');
    const panel = header.querySelector('.site-navigation');
    const mobile = window.matchMedia('(max-width: 1000px)');

    function setOpen(open) {
        header.classList.toggle('site-nav-open', open);
        toggle.setAttribute('aria-expanded', String(open));
        toggle.textContent = open
            ? '메뉴 닫기 ✕'
            : '메뉴 열기 ☰';
    }

    header.classList.add('site-nav-enhanced');
    toggle.hidden = false;

    toggle.addEventListener('click', () => {
        setOpen(
            toggle.getAttribute('aria-expanded') !== 'true'
        );
    });

    document.addEventListener('keydown', event => {
        if (
            event.key === 'Escape' &&
            header.classList.contains('site-nav-open')
        ) {
            setOpen(false);
            toggle.focus();
        }
    });

    document.addEventListener('click', event => {
        if (
            mobile.matches &&
            !header.contains(event.target)
        ) {
            setOpen(false);
        }
    });

    panel.addEventListener('click', event => {
        if (
            mobile.matches &&
            event.target.closest('a')
        ) {
            setOpen(false);
        }
    });

    mobile.addEventListener('change', () => {
        if (
            mobile.matches &&
            panel.contains(document.activeElement)
        ) {
            toggle.focus();
        }

        setOpen(false);
    });
})();
''',

    'home/static/home/site.css': r'''/* 사이트 공통 메뉴와 기본 디자인 */

body.site-shell {
  --ink:#17382d;
  --muted:#697b73;
  --line:#e1e9e4;
  --bg:#f4f7f5;
  --card:#fff;
  margin:0;
  background:var(--bg);
  color:var(--ink);
  color-scheme:light;
  font-family:system-ui,'Malgun Gothic','Apple SD Gothic Neo',sans-serif;
}

.site-shell .site-header,
.site-shell .site-header * {
  box-sizing:border-box;
}

.site-shell .site-header {
  position:sticky;
  top:0;
  z-index:80;
  width:100%;
  background:#075a35;
  color:#fff;
  border-bottom:1px solid #ffffff24;
  box-shadow:0 3px 16px #0b3b2512;
  line-height:1.5;
}

.site-shell .site-inner {
  max-width:1440px;
  margin:0 auto;
  padding:12px 24px;
  display:flex;
  align-items:center;
  gap:22px;
}

.site-shell .site-brand {
  display:flex;
  gap:9px;
  align-items:center;
  flex-shrink:0;
  color:#fff;
  text-decoration:none;
  font-size:18px;
  font-weight:850;
  letter-spacing:-.5px;
}

.site-shell .site-brand-icon {
  font-size:25px;
  line-height:1;
}

.site-shell .site-brand small {
  display:block;
  margin-top:2px;
  color:#b9d8c7;
  font-size:8px;
  letter-spacing:1.6px;
  font-weight:500;
}

.site-shell .site-navigation {
  display:flex;
  flex:1;
  align-items:center;
  justify-content:space-between;
  gap:16px;
  min-width:0;
}

.site-shell .site-links {
  display:flex;
  align-items:center;
  flex-wrap:wrap;
  gap:6px;
}

.site-shell .site-link {
  display:block;
  padding:9px 13px;
  border-radius:10px;
  color:#fff;
  font-size:13px;
  font-weight:650;
  text-decoration:none;
  white-space:nowrap;
  border:1px solid transparent;
  transition:background .15s;
}

.site-shell .site-link:hover {
  background:#ffffff1c;
}

.site-shell .site-link[aria-current="page"] {
  border-color:#fff;
  box-shadow:inset 0 -2px #fff;
}

.site-shell .site-link.site-best11 {
  background:#f2b705;
  color:#26350f;
  font-weight:800;
}

.site-shell .site-link.site-predict {
  background:#78e7ff;
  color:#073344;
  font-weight:800;
}

.site-shell .site-account {
  display:flex;
  align-items:center;
  justify-content:flex-end;
  gap:10px;
  margin-left:auto;
  flex-wrap:wrap;
  font-size:11px;
}

.site-shell .site-account a {
  color:#e1f1e8;
  text-decoration:none;
  white-space:nowrap;
  padding:5px 0;
}

.site-shell .site-account a:hover {
  text-decoration:underline;
}

.site-shell .site-user-name {
  max-width:100px;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
  color:#c8e6d5;
}

.site-shell .site-account form.site-logout {
  display:inline-flex;
  margin:0;
  padding:0;
  background:transparent;
  border:0;
  border-radius:0;
}

.site-shell .site-header .site-logout button,
.site-shell .site-nav-toggle {
  margin:0;
  padding:7px 11px;
  border:1px solid #ffffff40;
  border-radius:8px;
  background:#ffffff12;
  color:#fff;
  font:inherit;
  font-size:11px;
  font-weight:600;
  cursor:pointer;
  box-shadow:none;
  width:auto;
}

.site-shell .site-nav-toggle {
  display:none;
  margin-left:auto;
  font-size:12px;
}

.site-shell .site-header a:focus-visible,
.site-shell .site-header button:focus-visible {
  outline:3px solid #fff;
  outline-offset:3px;
}

.site-skip {
  position:fixed;
  top:8px;
  left:12px;
  z-index:10000;
  transform:translateY(-180%);
  background:white;
  color:#075a35;
  padding:10px 16px;
  border-radius:8px;
  font-weight:700;
}

.site-skip:focus {
  transform:translateY(0);
}

#site-page-content {
  scroll-margin-top:90px;
}

/* 선수 목록·상세 기본 디자인 */
.site-player-content {
  max-width:1180px;
  margin:0 auto;
  padding:30px 24px 60px;
  min-width:0;
}

.site-player-content h1 {
  font-size:28px;
  letter-spacing:-1px;
  margin:0 0 24px;
}

.site-player-content h2 {
  font-size:22px;
  margin-top:30px;
}

.site-player-content > form {
  display:flex;
  flex-wrap:wrap;
  align-items:center;
  gap:12px;
  padding:20px;
  border:1px solid var(--line);
  border-radius:14px;
  background:#fff;
}

.site-player-content select,
.site-player-content input,
.site-player-content button {
  font:inherit;
  border:1px solid #ccd9d1;
  border-radius:8px;
  padding:9px 12px;
  max-width:100%;
}

.site-player-content button {
  background:#168447;
  color:#fff;
  cursor:pointer;
  border-color:#168447;
}

.site-player-content a {
  color:#08783d;
  text-decoration:none;
  font-weight:650;
}

.site-player-content a:hover {
  text-decoration:underline;
}

.site-table-scroll {
  max-width:100%;
  overflow-x:auto;
  background:#fff;
  border:1px solid var(--line);
  border-radius:12px;
}

.site-player-content .site-table-scroll table {
  border:0;
  border-collapse:collapse;
  width:100%;
  font-size:13px;
  margin:0;
}

.site-player-content th,
.site-player-content td {
  border:0;
  border-bottom:1px solid #edf1ee;
  padding:13px 15px;
  text-align:left;
  white-space:nowrap;
}

.site-player-content th {
  background:#edf5ef;
  color:#466c57;
  font-size:12px;
}

.site-player-content tr:last-child td {
  border-bottom:0;
}

.site-player-content hr {
  border:0;
  border-top:1px solid var(--line);
  margin:24px 0;
}

.studio-title {
  font-size:18px;
  font-weight:800;
  color:#17382d;
  letter-spacing:-.5px;
}

@media (max-width:1200px) and (min-width:1001px) {
  .site-shell .site-inner {
    gap:14px;
    padding:12px 16px;
  }

  .site-shell .site-link {
    padding:8px 9px;
    font-size:12px;
  }

  .site-shell .site-account {
    gap:7px;
  }
}

@media (max-width:1000px) {
  .site-shell .site-inner {
    padding:12px 16px;
    flex-wrap:wrap;
    gap:12px;
  }

  .site-shell .site-nav-enhanced .site-nav-toggle {
    display:block;
  }

  .site-shell .site-navigation {
    width:100%;
    flex-basis:100%;
    flex-direction:column;
    align-items:stretch;
    gap:12px;
    padding-top:6px;
  }

  .site-shell .site-nav-enhanced:not(.site-nav-open) .site-navigation {
    display:none;
  }

  .site-shell .site-links {
    display:grid;
    grid-template-columns:repeat(2,minmax(0,1fr));
    gap:8px;
  }

  .site-shell .site-link {
    text-align:center;
    padding:11px 8px;
    font-size:13px;
  }

  .site-shell .site-account {
    width:100%;
    margin:0;
    justify-content:flex-start;
    border-top:1px solid #ffffff2a;
    padding-top:10px;
    gap:16px;
  }

  .site-player-content {
    padding:24px 16px 44px;
  }
}

@media (max-width:400px) {
  .site-shell .site-brand {
    font-size:16px;
  }

  .site-shell .site-brand-icon {
    font-size:21px;
  }

  .site-shell .site-nav-toggle {
    padding:7px 9px;
    font-size:11px;
  }

  .site-player-content h1 {
    font-size:24px;
  }
}

@media (prefers-reduced-motion:reduce) {
  .site-shell .site-link {
    transition:none;
  }
}
''',
}


PAGES = {
    'home/templates/index.html': 'home',
    'player/templates/player/best11.html': 'best11',
    'player/templates/plist.html': 'players',
    'player/templates/pview.html': 'players',
    'team/templates/team/lineup_simulation.html': 'predict',
    'team/templates/team/predict_match.html': 'predict',
    'board/templates/board/base.html': 'board',
}


def transform(relative, text, active):
    assets_marker = "include 'shared/site_assets.html'"
    header_marker = "include 'shared/site_header.html'"

    if assets_marker not in text:
        if text.count('</head>') != 1:
            raise ValueError(
                f'{relative}: </head> 위치를 확인할 수 없습니다.'
            )

        text = text.replace(
            '</head>',
            "{% include 'shared/site_assets.html' %}\n</head>",
            1,
        )

    if header_marker in text:
        return text

    if text.count('<body>') != 1:
        raise ValueError(
            f'{relative}: <body> 위치를 확인할 수 없습니다.'
        )

    if relative == 'home/templates/index.html':
        text, count = re.subn(
            r'<header\b[^>]*class="top"[^>]*>.*?</header>',
            '',
            text,
            count=1,
            flags=re.S,
        )

        if count != 1:
            raise ValueError(
                '메인페이지의 기존 상단 메뉴를 찾지 못했습니다.'
            )

    elif relative == 'board/templates/board/base.html':
        text, count = re.subn(
            r'<header\b[^>]*class="bd-head"[^>]*>.*?</header>',
            '',
            text,
            count=1,
            flags=re.S,
        )

        if count != 1:
            raise ValueError(
                '게시판의 기존 상단 메뉴를 찾지 못했습니다.'
            )

    elif relative == 'team/templates/team/lineup_simulation.html':
        text, count = re.subn(
            r'<a\b(?=[^>]*class="brand")(?=[^>]*href=)[^>]*>.*?</a>',
            '<span class="studio-title">선수 구성 시뮬레이션</span>',
            text,
            count=1,
            flags=re.S,
        )

        if count != 1:
            raise ValueError(
                '시뮬레이션 제목 위치를 찾지 못했습니다.'
            )

    elif relative == 'team/templates/team/predict_match.html':
        text, count = re.subn(
            r'(<main>).*?(<h1>)',
            r'\1\n    \2',
            text,
            count=1,
            flags=re.S,
        )

        if count != 1:
            raise ValueError(
                '기록 예측 화면의 제목 위치를 찾지 못했습니다.'
            )

    header = (
        "{% include 'shared/site_header.html' with active='"
        + active
        + "' %}"
    )

    text = text.replace(
        '<body>',
        '<body class="site-shell">\n' + header,
        1,
    )

    if relative in (
        'player/templates/plist.html',
        'player/templates/pview.html',
    ):
        text = text.replace(
            header,
            header + '\n<main class="site-player-content">',
            1,
        )

        text = text.replace(
            '</body>',
            '</main>\n</body>',
            1,
        )

        text = re.sub(
            r'(<table\b.*?</table>)',
            r'<div class="site-table-scroll">\1</div>',
            text,
            flags=re.S,
        )

    return text


def main():
    if not (ROOT / 'manage.py').is_file():
        raise SystemExit(
            'manage.py가 있는 team/project01 폴더에 '
            '이 파일을 저장하세요.'
        )

    planned = dict(FILES)

    # 모든 파일의 구조를 확인한 뒤 적용합니다.
    for relative, active in PAGES.items():
        path = ROOT / relative

        if not path.is_file():
            raise SystemExit(
                f'필요한 파일이 없습니다: {relative}'
            )

        planned[relative] = transform(
            relative,
            path.read_text(encoding='utf-8-sig'),
            active,
        )

    changed = {}
    originals = {}

    for relative, text in planned.items():
        path = ROOT / relative

        old = (
            path.read_bytes()
            if path.exists()
            else None
        )

        new = text.encode('utf-8')

        if old != new:
            changed[relative] = new
            originals[relative] = old

    if not changed:
        print('공통 메뉴가 이미 적용되어 있습니다.')
        return

    stamp = datetime.now().strftime(
        '%Y%m%d_%H%M%S_%f'
    )

    backup = ROOT / '.site_nav_backups' / stamp

    # 기존 파일 백업
    for relative, old in originals.items():
        if old is not None:
            target = backup / relative
            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            target.write_bytes(old)

    written = []

    try:
        for relative, content in changed.items():
            path = ROOT / relative

            path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            path.write_bytes(content)
            written.append(relative)

    except Exception:
        # 적용 도중 실패하면 이번에 변경한 파일을 되돌립니다.
        for relative in reversed(written):
            path = ROOT / relative
            old = originals[relative]

            if old is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(old)

        raise

    print(
        f'공통 메뉴 적용 완료: {len(changed)}개 파일'
    )
    print(
        f'기존 파일 백업: {backup}'
    )
    print(
        '다음: python manage.py check '
        '→ python manage.py runserver'
    )


if __name__ == '__main__':
    main()