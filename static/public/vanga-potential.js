(() => {
    const root = document.querySelector("[data-vanga-demo]");
    if (!root) return;

    const form = root.querySelector("[data-vanga-form]");
    const host = root.querySelector("[data-vanga-potential-host]");
    const predictUrlRaw = root.dataset.predictUrl || "";
    if (!form || !host || !predictUrlRaw || !window.fetch) return;

    const originalFetch = window.fetch.bind(window);
    const predictUrl = new URL(predictUrlRaw, window.location.origin).href;

    const value = (name) =>
        String(form.querySelector(`[name="${name}"]`)?.value || "").trim();

    const sourcePayload = () => {
        const source = {};
        const mapping = {
            source_type: "type",
            source_title: "title",
            source_author: "author",
            source_format: "format",
        };
        Object.entries(mapping).forEach(([field, key]) => {
            const item = value(field);
            if (item) source[key] = item;
        });
        const size = value("source_series_size");
        if (size) source.series_size = size;
        return source;
    };

    const renderProfile = (html, { scroll = false } = {}) => {
        host.innerHTML = html || "";
        if (!html) return;

        host.querySelectorAll("[data-vanga-reveal]").forEach((item) => {
            item.classList.add("is-visible");
        });

        if (scroll && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
            window.setTimeout(() => {
                host.scrollIntoView({ behavior: "smooth", block: "start" });
            }, 260);
        }
    };

    window.fetch = async (input, init = {}) => {
        const rawUrl = typeof input === "string" ? input : input?.url || "";
        const resolvedUrl = new URL(rawUrl, window.location.origin).href;
        let nextInit = init;
        let isPotentialPrediction = false;

        if (
            resolvedUrl === predictUrl &&
            String(init?.method || "GET").toUpperCase() === "POST" &&
            typeof init?.body === "string"
        ) {
            try {
                const body = JSON.parse(init.body);
                body.synopsis = value("synopsis");
                body.source = sourcePayload();
                nextInit = {
                    ...init,
                    body: JSON.stringify(body),
                };
                isPotentialPrediction = true;
            } catch {
                // Основной AJAX-контур сам покажет ошибку некорректного JSON.
            }
        }

        const response = await originalFetch(input, nextInit);

        if (isPotentialPrediction) {
            try {
                const data = await response.clone().json();
                if (data?.ok) {
                    renderProfile(data.profile_html || "", { scroll: false });
                }
            } catch {
                // Профиль является дополнительным слоем и не ломает прогноз.
            }
        }

        return response;
    };

    const snapshotMatch = window.location.pathname.match(
        /^\/demo\/vanga\/p\/([0-9a-f-]{36})\/?$/i
    );
    if (snapshotMatch) {
        originalFetch(`${window.location.pathname.replace(/\/$/, "")}/potential`, {
            method: "GET",
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        })
            .then((response) => response.json())
            .then((data) => {
                if (data?.ok && data.profile_html) {
                    renderProfile(data.profile_html);
                }
            })
            .catch(() => {
                // Старый snapshot может не содержать pre-release profile.
            });
    }
})();

(() => {
    // Future catalog — progressive enhancement. Если загрузка не удалась,
    // базовая форма Vanga остаётся полностью рабочей.
    const root = document.querySelector("[data-vanga-demo]");
    if (!root || document.querySelector("script[data-vanga-future-loader]")) return;

    if (!document.querySelector("link[data-vanga-future-style]")) {
        const style = document.createElement("link");
        style.rel = "stylesheet";
        style.href = "/static/public/vanga-future.css";
        style.dataset.vangaFutureStyle = "1";
        document.head.append(style);
    }

    const script = document.createElement("script");
    script.src = "/static/public/vanga-future.js";
    script.defer = true;
    script.dataset.vangaFutureLoader = "1";
    document.head.append(script);
})();
