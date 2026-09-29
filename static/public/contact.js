(() => {
    const form = document.querySelector('[data-contact-form]');
    if (!form || !window.fetch) {
        return;
    }

    const card = document.querySelector('[data-contact-card]');
    const transmission = form.querySelector('[data-contact-transmission]');
    const statusText = form.querySelector('[data-contact-status]');
    const progress = form.querySelector('[data-contact-progress]');
    const progressLabel = form.querySelector('[data-contact-progress-label]');
    const submit = form.querySelector('button[type="submit"]');
    const submitLabel = form.querySelector('[data-contact-submit-label]');
    const nonce = form.querySelector('[data-contact-nonce]');
    const errors = card?.querySelector('[data-contact-errors]');
    const success = card?.querySelector('[data-contact-success]');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const minSeconds = Math.max(0, Number(form.dataset.minSeconds || 0));
    let challengeIssuedAt = performance.now();
    let busy = false;

    const sleep = (milliseconds) => new Promise((resolve) => {
        window.setTimeout(resolve, milliseconds);
    });

    const wait = (milliseconds) => sleep(reducedMotion ? 0 : milliseconds);

    const setStage = (label, percent) => {
        statusText.textContent = label;
        progress.style.width = `${percent}%`;
        progressLabel.textContent = String(percent).padStart(2, '0') + '%';
    };

    const clearErrors = () => {
        if (!errors) {
            return;
        }
        errors.classList.add('is-empty');
        const list = errors.querySelector('ul');
        if (list) {
            list.replaceChildren();
        }
    };

    const showErrors = (messages) => {
        if (!errors) {
            return;
        }

        const list = errors.querySelector('ul');
        if (list) {
            list.replaceChildren(
                ...messages.map((message) => {
                    const item = document.createElement('li');
                    item.textContent = message;
                    return item;
                })
            );
        }
        errors.classList.remove('is-empty');
        errors.scrollIntoView({
            behavior: reducedMotion ? 'auto' : 'smooth',
            block: 'nearest'
        });
    };

    const refreshChallenge = async () => {
        try {
            const response = await fetch(window.location.pathname, {
                method: 'GET',
                credentials: 'same-origin',
                headers: {'Accept': 'text/html'}
            });
            if (!response.ok) {
                return;
            }
            const html = await response.text();
            const page = new DOMParser().parseFromString(html, 'text/html');
            const fresh = page.querySelector('[data-contact-nonce]');
            if (fresh && nonce) {
                nonce.value = fresh.value;
                challengeIssuedAt = performance.now();
            }
        } catch (_error) {
            // Ошибка обновления challenge не должна скрывать исходную ошибку отправки.
        }
    };

    const resetTurnstile = () => {
        if (window.turnstile && typeof window.turnstile.reset === 'function') {
            window.turnstile.reset();
        }
    };

    const unlock = () => {
        busy = false;
        form.classList.remove('is-submitting');
        form.removeAttribute('aria-busy');
        submit.disabled = false;
        submitLabel.textContent = 'Отправить сообщение';
    };

    form.addEventListener('submit', async (event) => {
        event.preventDefault();

        if (busy || !form.reportValidity()) {
            return;
        }

        busy = true;
        clearErrors();

        const payload = new FormData(form);
        const challengeAge = performance.now() - challengeIssuedAt;
        const antiSpamDelay = Math.max(0, minSeconds * 1000 - challengeAge + 120);

        form.classList.add('is-submitting');
        form.setAttribute('aria-busy', 'true');
        submit.disabled = true;
        submitLabel.textContent = 'Передаём…';
        transmission.hidden = false;
        setStage('Проверяем форму', 14);

        try {
            await wait(320);
            setStage('Проверяем защиту', 34);

            if (antiSpamDelay > 0) {
                // Это не декоративная задержка: сервер отклоняет слишком быструю
                // отправку challenge. Поэтому reduced-motion здесь не сокращает время.
                await sleep(antiSpamDelay);
            } else {
                await wait(360);
            }

            setStage('Передаём сообщение', 68);

            const response = await fetch(form.action || window.location.href, {
                method: 'POST',
                body: payload,
                credentials: 'same-origin',
                headers: {
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            const contentType = response.headers.get('content-type') || '';
            const data = contentType.includes('application/json')
                ? await response.json()
                : null;

            if (!response.ok || !data?.ok) {
                if (data?.contact_nonce && nonce) {
                    nonce.value = data.contact_nonce;
                    challengeIssuedAt = performance.now();
                } else {
                    await refreshChallenge();
                }

                const messages = Array.isArray(data?.errors) && data.errors.length
                    ? data.errors
                    : ['Не удалось подтвердить отправку. Проверьте соединение и повторите попытку.'];

                setStage('Передача остановлена', 0);
                showErrors(messages);
                resetTurnstile();
                await wait(260);
                transmission.hidden = true;
                unlock();
                return;
            }

            setStage('Подтверждаем приём', 88);
            await wait(420);
            setStage('Принято системой', 100);
            await wait(620);

            form.classList.add('is-complete');
            await wait(300);
            form.hidden = true;

            if (success) {
                success.hidden = false;
                requestAnimationFrame(() => success.classList.add('is-visible'));
                success.focus?.({preventScroll: true});
            }
        } catch (_error) {
            await refreshChallenge();
            setStage('Связь прервана', 0);
            showErrors([
                'Соединение прервалось до подтверждения. Проверьте сеть и повторите отправку.'
            ]);
            resetTurnstile();
            await wait(260);
            transmission.hidden = true;
            unlock();
        }
    });
})();
