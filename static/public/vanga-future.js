(() => {
    const root = document.querySelector("[data-vanga-demo]");
    if (!root || !window.fetch) return;

    const shell = root.querySelector(".vanga-demo__shell");
    const form = root.querySelector("[data-vanga-form]");
    if (!shell || !form) return;

    const catalogUrl = "/demo/vanga/future-catalog";
    const payloadUrl = "/demo/vanga/future-payload";
    const csrf = () => form.querySelector("[data-vanga-csrf]")?.value || "";
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const territoryLabels = {
        DE: "Германия",
        US: "США",
        NL: "Нидерланды",
        GB: "Великобритания",
        FR: "Франция",
        ES: "Испания",
        IT: "Италия",
        CA: "Канада",
        AU: "Австралия",
        JP: "Япония",
        KR: "Южная Корея",
    };

    const blockerLabels = {
        regional_release_date_conflict: "Источники расходятся по дате релиза",
        regional_release_date_missing: "Для выбранного рынка пока нет подтверждённой даты",
        regional_exact_release_date_missing: "Дата известна только приблизительно",
        director_missing: "Пока не известен режиссёр",
        runtime_missing: "Пока не известен хронометраж",
        genres_missing: "Пока не известны жанры",
        runtime_fact_conflict: "Источники расходятся по хронометражу",
        genres_fact_conflict: "Источники расходятся по жанрам",
        cutoff_must_be_pre_release: "Фильм уже вышел на выбранном рынке",
    };

    const resolutionLabels = {
        resolved: "дата подтверждена",
        conflict: "есть конфликт источников",
        mapping_incomplete: "регион источника ещё уточняется",
        missing: "региональная дата отсутствует",
    };

    const section = document.createElement("section");
    section.className = "vanga-future";
    section.dataset.vangaFuture = "";
    section.innerHTML = `
        <div class="vanga-future__head">
            <div>
                <span class="vanga-demo__eyebrow">Будущие релизы</span>
                <h2>Что Vanga уже знает до премьеры</h2>
                <p>Каталог строится только из сведений, известных на текущий момент. Дата релиза выбирается для конкретного рынка и не подменяется условным worldwide.</p>
            </div>
            <label class="vanga-future__market">
                <span>Рынок релиза</span>
                <select data-vanga-future-territory>
                    ${Object.entries(territoryLabels)
                        .map(([code, label]) => `<option value="${code}">${label} · ${code}</option>`)
                        .join("")}
                </select>
            </label>
        </div>
        <div class="vanga-future__status" data-vanga-future-status>Загружаю будущие релизы…</div>
        <div class="vanga-future__grid" data-vanga-future-grid></div>
    `;

    const anchor = shell.querySelector(".vanga-demo__grid");
    shell.insertBefore(section, anchor || shell.firstChild);

    const territorySelect = section.querySelector("[data-vanga-future-territory]");
    const status = section.querySelector("[data-vanga-future-status]");
    const grid = section.querySelector("[data-vanga-future-grid]");

    const savedTerritory = (() => {
        try {
            return window.localStorage.getItem("jsint:vanga:territory") || "";
        } catch {
            return "";
        }
    })();
    if (territoryLabels[savedTerritory]) territorySelect.value = savedTerritory;

    const escapeHtml = (value) => {
        const node = document.createElement("div");
        node.textContent = String(value ?? "");
        return node.innerHTML;
    };

    const formatDate = (value) => {
        if (!value) return "Дата уточняется";
        const parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) return "Дата уточняется";
        return parsed.toLocaleDateString("ru-RU", {
            day: "numeric",
            month: "long",
            year: "numeric",
        });
    };

    const evidenceSummary = (item) => {
        const evidence = item?.release_window?.evidence || [];
        const sources = [...new Set(evidence.map((entry) => entry.source_id).filter(Boolean))];
        if (!sources.length) return "Источник даты пока не сопоставлен";
        if (sources.length === 1) return "1 источник даты";
        return `${sources.length} независимых источника даты`;
    };

    const setFormValue = (name, value) => {
        const field = form.querySelector(`[name="${name}"]`);
        if (!field) return;
        field.value = value ?? "";
        field.dispatchEvent(new Event("input", { bubbles: true }));
        field.dispatchEvent(new Event("change", { bubbles: true }));
    };

    const fillForm = (requestPayload) => {
        const payload = requestPayload || {};
        setFormValue("imdb_id", payload.imdb_id || "");
        setFormValue("title", payload.title || "");
        setFormValue("director", payload.director || payload.directors?.[0] || "");
        setFormValue("writer", payload.writer || "");
        setFormValue("year", payload.year || "");
        setFormValue("runtime", payload.runtime || "");
        setFormValue("genres", Array.isArray(payload.genres) ? payload.genres.join(", ") : payload.genres || "");
        setFormValue("actors", Array.isArray(payload.actors) ? payload.actors.join(", ") : payload.actors || "");
        setFormValue("synopsis", payload.synopsis || "");

        const source = payload.source && typeof payload.source === "object" ? payload.source : {};
        setFormValue("source_type", source.type || "");
        setFormValue("source_title", source.title || "");
        setFormValue("source_author", source.author || "");
        setFormValue("source_format", source.format || "");
        setFormValue("source_series_size", source.series_size || "");
    };

    const renderBlocked = (card, payload) => {
        const host = card.querySelector("[data-vanga-future-card-status]");
        const blockers = Array.isArray(payload?.blockers) ? payload.blockers : [];
        const warnings = Array.isArray(payload?.warnings) ? payload.warnings : [];
        const lines = blockers.map((key) => blockerLabels[key] || key);
        if (warnings.includes("regional_release_mapping_incomplete")) {
            lines.push("Есть дата с ещё не сопоставленной территорией источника");
        }
        host.className = "vanga-future-card__message is-warning";
        host.textContent = lines.join(" · ") || "Данных пока недостаточно для прогноза";
    };

    const runFuturePrediction = async (item, card, button) => {
        button.disabled = true;
        button.textContent = "Проверяю данные…";
        const message = card.querySelector("[data-vanga-future-card-status]");
        message.className = "vanga-future-card__message";
        message.textContent = "Собираю temporal-safe данные для выбранного рынка…";

        try {
            const response = await fetch(payloadUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    Accept: "application/json",
                    "X-CSRF-Token": csrf(),
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: JSON.stringify({
                    project_id: item.project_id,
                    territory: territorySelect.value,
                    cutoff: new Date().toISOString(),
                }),
            });
            const data = await response.json();
            if (!response.ok || !data.ok) {
                throw new Error(data.error || "Не удалось проверить будущий проект");
            }
            if (!data.prediction_ready || !data.request) {
                renderBlocked(card, data);
                return;
            }

            fillForm(data.request);
            message.className = "vanga-future-card__message is-ready";
            message.textContent = "Данных достаточно. Запускаю прогноз для выбранного рынка.";
            form.requestSubmit();
            if (!reducedMotion) {
                window.setTimeout(() => {
                    form.scrollIntoView({ behavior: "smooth", block: "start" });
                }, 120);
            }
        } catch (error) {
            message.className = "vanga-future-card__message is-error";
            message.textContent = error?.message || "Future catalog временно недоступен";
        } finally {
            button.disabled = false;
            button.textContent = "Проверить и спрогнозировать";
        }
    };

    const renderCatalog = (items) => {
        grid.replaceChildren();
        if (!items.length) {
            status.textContent = "Для выбранного рынка в локальном реестре пока нет будущих релизов.";
            return;
        }
        status.textContent = `Найдено будущих проектов: ${items.length}. Данные не запрашиваются из сети во время прогноза.`;

        items.slice(0, 12).forEach((item) => {
            const resolution = item.regional_release_resolution || "missing";
            const card = document.createElement("article");
            card.className = `vanga-future-card is-${resolution}`;
            const releaseText = formatDate(item.release_at || item.release_window?.release_start_at);
            card.innerHTML = `
                <div class="vanga-future-card__top">
                    <span>${escapeHtml(territoryLabels[territorySelect.value] || territorySelect.value)}</span>
                    <b>${escapeHtml(resolutionLabels[resolution] || resolution)}</b>
                </div>
                <h3>${escapeHtml(item.canonical_title || "Будущий фильм")}</h3>
                <strong class="vanga-future-card__date">${escapeHtml(releaseText)}</strong>
                <p>${escapeHtml(evidenceSummary(item))}</p>
                <div class="vanga-future-card__message" data-vanga-future-card-status></div>
                <button type="button" data-vanga-future-predict>Проверить и спрогнозировать</button>
            `;
            card.querySelector("[data-vanga-future-predict]")?.addEventListener("click", (event) => {
                runFuturePrediction(item, card, event.currentTarget);
            });
            grid.append(card);
        });
    };

    let controller = null;
    const loadCatalog = async () => {
        controller?.abort();
        controller = new AbortController();
        grid.replaceChildren();
        status.className = "vanga-future__status is-loading";
        status.textContent = "Загружаю future catalog…";

        try {
            const url = new URL(catalogUrl, window.location.origin);
            url.searchParams.set("territory", territorySelect.value);
            url.searchParams.set("cutoff", new Date().toISOString());
            const response = await fetch(url, {
                method: "GET",
                credentials: "same-origin",
                headers: { Accept: "application/json" },
                signal: controller.signal,
            });
            const data = await response.json();
            if (!response.ok || !data.ok) {
                throw new Error(data.error || "Future catalog временно недоступен");
            }
            status.className = "vanga-future__status";
            renderCatalog(Array.isArray(data.items) ? data.items : []);
        } catch (error) {
            if (error?.name === "AbortError") return;
            status.className = "vanga-future__status is-error";
            status.textContent = `${error?.message || "Future catalog временно недоступен"}. Ручной прогноз ниже продолжает работать.`;
        }
    };

    territorySelect.addEventListener("change", () => {
        try {
            window.localStorage.setItem("jsint:vanga:territory", territorySelect.value);
        } catch {
            // localStorage может быть недоступен в приватном режиме.
        }
        loadCatalog();
    });

    loadCatalog();
})();
