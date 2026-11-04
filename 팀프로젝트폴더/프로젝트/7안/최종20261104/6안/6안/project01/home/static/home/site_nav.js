(() => {
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
