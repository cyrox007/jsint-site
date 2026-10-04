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

    const parseNames = (raw, limit) => {
        const result = [];
        String(raw || "")
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean)
            .forEach((item) => {
                if (!result.includes(item) && result.length < limit) result.push(item);
            });
        return result;
    };

    const extraTeam = (role) => {
        const field = form.querySelector(`[data-vanga-team-values="${role}"]`);
        if (!field?.value) return [];
        try {
            const values = JSON.parse(field.value);
            return Array.isArray(values) ? values.map((item) => String(item).trim()).filter(Boolean) : [];
        } catch {
            return [];
        }
    };

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
                const primaryDirector = value("director");
                const directors = [primaryDirector, ...extraTeam("director")]
                    .map((item) => String(item || "").trim())
                    .filter((item, index, all) => item && all.indexOf(item) === index)
                    .slice(0, 8);
                const actors = [
                    ...parseNames(value("actors"), 32),
                    ...extraTeam("actor"),
                ]
                    .filter((item, index, all) => item && all.indexOf(item) === index)
                    .slice(0, 32);

                body.director = directors[0] || primaryDirector;
                body.directors = directors;
                body.actors = actors;
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
    const root = document.querySelector("[data-vanga-demo]");
    if (!root) return;

    const loadStyle = (href, marker) => {
        if (document.querySelector(`link[${marker}]`)) return;
        const style = document.createElement("link");
        style.rel = "stylesheet";
        style.href = href;
        style.setAttribute(marker, "1");
        document.head.append(style);
    };

    const loadScript = (src, marker) => {
        if (document.querySelector(`script[${marker}]`)) return;
        const script = document.createElement("script");
        script.src = src;
        script.defer = true;
        script.setAttribute(marker, "1");
        document.head.append(script);
    };

    // Оба блока являются progressive enhancement: при ошибке загрузки
    // основная ручная форма и prediction остаются рабочими.
    loadStyle("/static/public/vanga-future.css", "data-vanga-future-style");
    loadScript("/static/public/vanga-future.js", "data-vanga-future-loader");
    loadStyle("/static/public/vanga-team.css", "data-vanga-team-style");
    loadScript("/static/public/vanga-team.js", "data-vanga-team-loader");
})();
