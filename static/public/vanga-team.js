(() => {
    const root = document.querySelector("[data-vanga-demo]");
    const form = root?.querySelector("[data-vanga-form]");
    const searchUrl = root?.dataset.searchUrl || "";
    if (!root || !form || !searchUrl || !window.fetch) return;

    const primaryDirector = form.querySelector('[name="director"]');
    const primaryActors = form.querySelector('[name="actors"]');
    if (!primaryDirector || !primaryActors) return;

    const unique = (items, limit) => {
        const result = [];
        items.forEach((item) => {
            const clean = String(item || "").trim();
            if (clean && !result.includes(clean) && result.length < limit) result.push(clean);
        });
        return result;
    };

    const createBlock = ({ role, title, hint, limit }) => {
        const block = document.createElement("div");
        block.className = "vanga-team-extra";
        block.dataset.vangaTeamRole = role;

        const head = document.createElement("div");
        head.className = "vanga-team-extra__head";
        head.innerHTML = `<strong>${title}</strong><small>${hint}</small>`;

        const chips = document.createElement("div");
        chips.className = "vanga-team-extra__chips";

        const search = document.createElement("div");
        search.className = "vanga-team-extra__search";
        const input = document.createElement("input");
        input.type = "text";
        input.autocomplete = "off";
        input.placeholder = role === "director" ? "Добавить ещё режиссёра" : "Добавить актёра в расширенный состав";
        const suggestions = document.createElement("div");
        suggestions.className = "vanga-team-extra__suggestions";
        suggestions.hidden = true;
        search.append(input, suggestions);

        const hidden = document.createElement("input");
        hidden.type = "hidden";
        hidden.dataset.vangaTeamValues = role;

        const items = [];
        const sync = () => {
            hidden.value = JSON.stringify(items);
            chips.replaceChildren();
            items.forEach((name, index) => {
                const chip = document.createElement("span");
                chip.className = "vanga-team-extra__chip";
                const label = document.createElement("b");
                label.textContent = `${index + 2}. ${name}`;
                const remove = document.createElement("button");
                remove.type = "button";
                remove.setAttribute("aria-label", `Убрать ${name}`);
                remove.textContent = "×";
                remove.addEventListener("click", () => {
                    items.splice(index, 1);
                    sync();
                });
                chip.append(label, remove);
                chips.append(chip);
            });
            input.disabled = items.length >= limit;
        };

        let timer = 0;
        let controller = null;
        input.addEventListener("input", () => {
            window.clearTimeout(timer);
            const query = input.value.trim();
            if (query.length < 2) {
                suggestions.hidden = true;
                suggestions.replaceChildren();
                return;
            }
            timer = window.setTimeout(async () => {
                controller?.abort();
                controller = new AbortController();
                try {
                    const url = new URL(searchUrl, window.location.origin);
                    url.searchParams.set("type", "person");
                    url.searchParams.set("role", role);
                    url.searchParams.set("q", query);
                    const response = await fetch(url, {
                        credentials: "same-origin",
                        headers: { Accept: "application/json" },
                        signal: controller.signal,
                    });
                    const data = await response.json();
                    if (!response.ok || !data.ok) throw new Error(data.error || "Поиск недоступен");
                    suggestions.replaceChildren();
                    const currentPrimary = role === "director"
                        ? primaryDirector.value.trim()
                        : primaryActors.value.split(",").map((item) => item.trim()).filter(Boolean);
                    const primaryList = Array.isArray(currentPrimary) ? currentPrimary : [currentPrimary];
                    const candidates = (data.items || []).filter(
                        (item) => item?.name && !items.includes(item.name) && !primaryList.includes(item.name)
                    );
                    candidates.slice(0, 8).forEach((item) => {
                        const button = document.createElement("button");
                        button.type = "button";
                        button.innerHTML = `<strong></strong><small></small>`;
                        button.querySelector("strong").textContent = item.name;
                        button.querySelector("small").textContent = item.imdb_id || "";
                        button.addEventListener("click", () => {
                            if (items.length < limit) items.push(item.name);
                            input.value = "";
                            suggestions.hidden = true;
                            sync();
                        });
                        suggestions.append(button);
                    });
                    suggestions.hidden = !candidates.length;
                } catch (error) {
                    if (error?.name !== "AbortError") suggestions.hidden = true;
                }
            }, 260);
        });

        block.append(head, chips, search, hidden);
        return block;
    };

    const directorBlock = createBlock({
        role: "director",
        title: "Режиссёрская команда",
        hint: "Основной режиссёр указан выше; можно добавить ещё до 7 человек в порядке credits.",
        limit: 7,
    });
    primaryDirector.closest(".vanga-field")?.after(directorBlock);

    const castBlock = createBlock({
        role: "actor",
        title: "Расширенный principal cast",
        hint: "Основное поле остаётся быстрым вводом; сюда можно добавить состав до общего лимита 32 человек.",
        limit: 27,
    });
    primaryActors.closest(".vanga-field")?.after(castBlock);

    const actorHint = primaryActors.closest(".vanga-field")?.querySelector("small");
    if (actorHint) {
        actorHint.textContent = "Основные имена через запятую. Расширенный состав добавляется ниже и передаётся модели полностью.";
    }
})();
