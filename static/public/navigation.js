(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    document.addEventListener('click', (event) => {
        const link = event.target.closest('a[href]');
        if (!link) {
            return;
        }

        const url = new URL(link.href, window.location.href);
        if (
            url.origin !== window.location.origin ||
            url.pathname !== window.location.pathname ||
            !url.hash ||
            url.hash === '#'
        ) {
            return;
        }

        let target;
        try {
            target = document.getElementById(decodeURIComponent(url.hash.slice(1)));
        } catch (_error) {
            return;
        }
        if (!target) {
            event.preventDefault();
            return;
        }

        event.preventDefault();
        target.scrollIntoView({
            behavior: reduceMotion ? 'auto' : 'smooth',
            block: 'start'
        });
        window.history.pushState(null, '', url.hash);
    });
})();
