(() => {
    const root = document.querySelector("[data-vanga-demo]");
    const form = root?.querySelector("[data-vanga-form]");
    if (!root || !form) return;

    const titleInput = form.querySelector("[data-vanga-movie-search]");
    const titleField = titleInput?.closest("label");
    const submit = form.querySelector("[data-vanga-submit]");
    if (!titleInput || !titleField || !submit) return;

    root.dataset.vangaMode = "simple";
    titleField.dataset.vangaSimpleSearch = "";

    const advancedNodes = [
        form.querySelector('[name="director"]')?.closest("label"),
        form.querySelector('[name="writer"]')?.closest("label"),
        form.querySelector('[name="year"]')?.closest(".vanga-form__row"),
        form.querySelector('[name="genres"]')?.closest("label"),
        form.querySelector('[name="actors"]')?.closest("label"),
        form.querySelector('[name="synopsis"]')?.closest("label"),
        form.querySelector(".vanga-source"),
    ].filter(Boolean);

    advancedNodes.forEach((node) => {
        node.classList.add("vanga-advanced-control");
        node.dataset.vangaAdvancedContent = "";
    });

    const style = document.createElement("style");
    style.textContent = `
        .vanga-mode-switch{display:grid;gap:10px;margin:-2px 0 2px}
        .vanga-mode-switch__hint{margin:0;color:#6f899d;font-size:12px;line-height:1.5}
        .vanga-mode-switch__button{display:flex;align-items:center;justify-content:space-between;gap:14px;width:100%;padding:13px 15px;border:1px solid rgba(118,153,195,.14);border-radius:14px;background:rgba(5,17,31,.52);color:#c9d9e5;font:inherit;font-size:13px;font-weight:750;cursor:pointer;transition:border-color .2s ease,background .2s ease,transform .2s ease}
        .vanga-mode-switch__button:hover{border-color:rgba(91,204,225,.34);background:rgba(7,25,42,.76);transform:translateY(-1px)}
        .vanga-mode-switch__button span:last-child{color:#6f899d;font-size:11px;font-weight:650}
        .vanga-demo:not(.is-advanced) .vanga-advanced-control{display:none!important}
        .vanga-demo:not(.is-advanced) .vanga-future{display:none!important}
        .vanga-demo:not(.is-advanced) .vanga-compare{display:none!important}
        .vanga-simple-warning{margin:0;padding:10px 12px;border:1px solid rgba(229,140,152,.22);border-radius:11px;background:rgba(89,27,39,.18);color:#e7a0aa;font-size:12px;line-height:1.45}
        .vanga-demo.is-advanced .vanga-mode-switch__hint{color:#83a1b7}
        @media (max-width:680px){.vanga-mode-switch__button{align-items:flex-start;text-align:left}.vanga-mode-switch__button span:last-child{text-align:right}}
    `;
    document.head.append(style);

    const switcher = document.createElement("div");
    switcher.className = "vanga-mode-switch";
    switcher.innerHTML = `
        <p class="vanga-mode-switch__hint" data-vanga-mode-hint>Выберите фильм из подсказок — режиссёра, год, жанры и остальные известные параметры Vanga подставит сама.</p>
        <button class="vanga-mode-switch__button" type="button" aria-expanded="false" data-vanga-advanced>
            <span>Расширенный режим</span>
            <span data-vanga-mode-label>тонкие настройки</span>
        </button>
    `;
    titleField.insertAdjacentElement("afterend", switcher);

    const heading = form.querySelector(".vanga-form__head strong");
    if (heading) heading.textContent = "Найдите фильм и получите прогноз";

    const submitLabel = submit.querySelector(".vanga-form__submit-label");
    if (submitLabel) submitLabel.textContent = "Получить прогноз";

    const toggle = switcher.querySelector("[data-vanga-advanced]");
    const modeLabel = switcher.querySelector("[data-vanga-mode-label]");
    const hint = switcher.querySelector("[data-vanga-mode-hint]");

    let futureAssetsRequested = false;
    const ensureFutureAssets = () => {
        if (futureAssetsRequested) return;
        futureAssetsRequested = true;

        if (!document.querySelector('link[data-vanga-future-style]')) {
            const link = document.createElement("link");
            link.rel = "stylesheet";
            link.href = "/static/public/vanga-future.css";
            link.dataset.vangaFutureStyle = "";
            document.head.append(link);
        }

        if (!document.querySelector('script[data-vanga-future-script]') && !document.querySelector('.vanga-future')) {
            const script = document.createElement("script");
            script.src = "/static/public/vanga-future.js";
            script.defer = true;
            script.dataset.vangaFutureScript = "";
            document.body.append(script);
        }
    };

    const setAdvanced = (enabled) => {
        root.classList.toggle("is-advanced", enabled);
        root.dataset.vangaMode = enabled ? "advanced" : "simple";
        toggle.setAttribute("aria-expanded", enabled ? "true" : "false");
        modeLabel.textContent = enabled ? "скрыть настройки" : "тонкие настройки";
        hint.textContent = enabled
            ? "Можно вручную изменить команду, параметры фильма, синопсис, первоисточник и использовать каталог будущих релизов."
            : "Выберите фильм из подсказок — режиссёра, год, жанры и остальные известные параметры Vanga подставит сама.";
        if (enabled) ensureFutureAssets();
    };

    toggle.addEventListener("click", () => {
        setAdvanced(!root.classList.contains("is-advanced"));
    });

    const requiredAdvancedFields = ["director", "year", "runtime", "genres"];
    const missingAutofilledFields = () => requiredAdvancedFields.filter((name) => {
        const field = form.elements.namedItem(name);
        return !field || !String(field.value || "").trim();
    });

    const clearWarning = () => form.querySelector("[data-vanga-simple-warning]")?.remove();

    form.addEventListener("submit", (event) => {
        clearWarning();
        if (root.classList.contains("is-advanced")) return;

        const missing = missingAutofilledFields();
        if (!missing.length) return;

        event.preventDefault();
        const warning = document.createElement("p");
        warning.className = "vanga-simple-warning";
        warning.dataset.vangaSimpleWarning = "";
        warning.textContent = "Выберите фильм из выпадающих подсказок, чтобы Vanga автоматически заполнила данные. Для ручного ввода откройте расширенный режим.";
        switcher.insertAdjacentElement("afterend", warning);
        titleInput.focus();
    });

    titleInput.addEventListener("input", clearWarning);

    const observer = new MutationObserver(() => {
        const future = root.querySelector(".vanga-future");
        if (future) future.dataset.vangaAdvancedContent = "";
    });
    observer.observe(root, { childList: true, subtree: true });

    setAdvanced(false);
})();
