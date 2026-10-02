(() => {
    const root = document.querySelector("[data-vanga-demo]");
    if (!root) return;

    const form = root.querySelector("[data-vanga-form]");
    const result = root.querySelector("[data-vanga-result]");
    const analysisHost = root.querySelector("[data-vanga-analysis-host]");
    const searchUrl = root.dataset.searchUrl || "";
    const predictUrl = root.dataset.predictUrl || "";
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const historyKey = "jsint:vanga:history:v1";

    const debounce = (fn, delay = 260) => {
        let timer = 0;
        return (...args) => {
            window.clearTimeout(timer);
            timer = window.setTimeout(() => fn(...args), delay);
        };
    };

    const escapeHtml = (value) => {
        const node = document.createElement("div");
        node.textContent = String(value ?? "");
        return node.innerHTML;
    };

    const initReveal = (scope = root) => {
        const targets = [...scope.querySelectorAll("[data-vanga-reveal]")];
        if (!targets.length) return;

        if (reducedMotion || !("IntersectionObserver" in window)) {
            targets.forEach((item) => item.classList.add("is-visible"));
            return;
        }

        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (!entry.isIntersecting) return;
                    entry.target.classList.add("is-visible");
                    observer.unobserve(entry.target);
                });
            },
            { threshold: 0.14 }
        );
        targets.forEach((item) => observer.observe(item));
    };

    const initCardGlow = (scope = root) => {
        if (reducedMotion) return;
        scope.querySelectorAll(".vanga-card").forEach((card) => {
            if (card.dataset.vangaGlowReady === "1") return;
            card.dataset.vangaGlowReady = "1";
            card.addEventListener("pointermove", (event) => {
                const rect = card.getBoundingClientRect();
                const x = ((event.clientX - rect.left) / rect.width) * 100;
                const y = ((event.clientY - rect.top) / rect.height) * 100;
                card.style.setProperty("--mx", `${x}%`);
                card.style.setProperty("--my", `${y}%`);
            });
        });
    };

    const animatePrediction = ({ scroll = true } = {}) => {
        if (!result || !result.classList.contains("has-prediction")) return;

        result.classList.remove("is-visible");
        window.requestAnimationFrame(() => {
            window.requestAnimationFrame(() => result.classList.add("is-visible"));
        });

        const ratingNode = result.querySelector("[data-rating-value]");
        const ratingRing = result.querySelector("[data-rating-ring]");
        const rating = Number(
            ratingNode?.dataset.rating || ratingRing?.dataset.rating || 0
        );

        if (ratingRing) {
            const angle = Math.max(0, Math.min(10, rating)) * 36;
            ratingRing.style.setProperty("--rating-angle", "0deg");
            window.requestAnimationFrame(() => {
                window.requestAnimationFrame(() => {
                    ratingRing.style.setProperty("--rating-angle", `${angle}deg`);
                });
            });
        }

        if (ratingNode) {
            if (reducedMotion) {
                ratingNode.textContent = rating.toFixed(2);
            } else {
                ratingNode.textContent = "0.00";
                const duration = 950;
                const start = performance.now();
                const tick = (now) => {
                    const progress = Math.min(1, (now - start) / duration);
                    const eased = 1 - Math.pow(1 - progress, 3);
                    ratingNode.textContent = (rating * eased).toFixed(2);
                    if (progress < 1) window.requestAnimationFrame(tick);
                };
                window.requestAnimationFrame(tick);
            }
        }

        result.querySelectorAll("[data-vanga-impact]").forEach((item) => {
            const strength = Math.max(
                0,
                Math.min(100, Number(item.dataset.strength || 0))
            );
            const bar = item.querySelector(".vanga-impact__track i");
            if (!bar) return;
            bar.style.width = "0";
            window.requestAnimationFrame(() => {
                bar.style.width = `${strength}%`;
            });
        });

        if (scroll && !reducedMotion) {
            window.setTimeout(() => {
                result.scrollIntoView({ behavior: "smooth", block: "center" });
            }, 160);
        }
    };

    const initFactors = (scope = root) => {
        const factors = [...scope.querySelectorAll("[data-vanga-factor]")];
        const show = (item, index = 0) => {
            const strength = Math.max(
                0,
                Math.min(100, Number(item.dataset.strength || 0))
            );
            const bar = item.querySelector(".vanga-factor-card__impact i");
            const delay = reducedMotion ? 0 : Math.min(index * 35, 280);
            window.setTimeout(() => {
                item.classList.add("is-visible");
                if (bar) bar.style.width = `${strength}%`;
            }, delay);
        };

        if (!factors.length) return;
        if (reducedMotion || !("IntersectionObserver" in window)) {
            factors.forEach(show);
            return;
        }

        const observer = new IntersectionObserver(
            (entries) => {
                entries
                    .filter((entry) => entry.isIntersecting)
                    .forEach((entry, index) => {
                        show(entry.target, index);
                        observer.unobserve(entry.target);
                    });
            },
            { threshold: 0.12 }
        );
        factors.forEach((item) => observer.observe(item));
    };

    const initDynamicContent = ({ scroll = false } = {}) => {
        initReveal(root);
        initCardGlow(root);
        animatePrediction({ scroll });
        initFactors(root);
    };

    const input = (name) => form?.querySelector(`[name="${name}"]`);
    const movieInput = root.querySelector("[data-vanga-movie-search]");
    const directorInput = root.querySelector(
        '[data-vanga-person-search][data-role="director"]'
    );
    const actorsInput = root.querySelector(
        '[data-vanga-person-search][data-role="actor"]'
    );
    const movieSuggestions = root.querySelector("[data-vanga-movie-suggestions]");
    const directorSuggestions = root.querySelector(
        "[data-vanga-director-suggestions]"
    );
    const actorSuggestions = root.querySelector("[data-vanga-actor-suggestions]");
    const imdbInput = root.querySelector("[data-vanga-imdb-id]");
    const selectedMovie = root.querySelector("[data-vanga-selected-movie]");
    const genresInput = root.querySelector("[data-vanga-genres]");
    const genreChips = [...root.querySelectorAll("[data-vanga-genre]")];

    const requiredInputs = form
        ? [...form.querySelectorAll("input[required]")]
        : [];
    const progress = form?.querySelector("[data-vanga-form-progress]");

    const refreshProgress = () => {
        if (!progress) return;
        const completed = requiredInputs.filter((field) => field.value.trim()).length;
        const value = requiredInputs.length
            ? Math.round((completed / requiredInputs.length) * 100)
            : 0;
        progress.style.width = `${value}%`;
    };

    const normalizedGenres = () =>
        (genresInput?.value || "")
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean);

    const refreshGenreChips = () => {
        const selected = new Set(
            normalizedGenres().map((value) => value.toLocaleLowerCase())
        );
        genreChips.forEach((chip) => {
            const active = selected.has(
                String(chip.dataset.vangaGenre || "").toLocaleLowerCase()
            );
            chip.classList.toggle("is-active", active);
            chip.setAttribute("aria-pressed", active ? "true" : "false");
        });
    };

    genreChips.forEach((chip) => {
        chip.setAttribute("aria-pressed", "false");
        chip.addEventListener("click", () => {
            if (!genresInput) return;
            const value = String(chip.dataset.vangaGenre || "").trim();
            if (!value) return;

            const items = normalizedGenres();
            const index = items.findIndex(
                (item) => item.toLocaleLowerCase() === value.toLocaleLowerCase()
            );
            if (index >= 0) {
                items.splice(index, 1);
            } else {
                items.push(value);
            }
            genresInput.value = items.join(", ");
            genresInput.dispatchEvent(new Event("input", { bubbles: true }));
            refreshGenreChips();
        });
    });

    genresInput?.addEventListener("input", refreshGenreChips);

    requiredInputs.forEach((field) => {
        field.addEventListener("input", refreshProgress);
        field.addEventListener("change", refreshProgress);
    });
    refreshProgress();
    refreshGenreChips();

    const closeSuggest = (container, field) => {
        if (container) {
            container.hidden = true;
            container.replaceChildren();
        }
        field?.setAttribute("aria-expanded", "false");
    };

    const renderMovieSuggestions = (items) => {
        if (!movieSuggestions || !movieInput) return;
        movieSuggestions.replaceChildren();

        if (!items.length) {
            const empty = document.createElement("div");
            empty.className = "vanga-suggest__empty";
            empty.textContent = "Совпадений в локальном IMDb пока нет";
            movieSuggestions.append(empty);
            movieSuggestions.hidden = false;
            movieInput.setAttribute("aria-expanded", "true");
            return;
        }

        items.forEach((item) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "vanga-suggest__item";
            button.setAttribute("role", "option");

            const title = document.createElement("strong");
            title.textContent = item.title || "Без названия";

            const meta = document.createElement("span");
            const bits = [
                item.year || null,
                item.director || null,
                item.genres?.slice(0, 3).join(" · ") || null,
            ].filter(Boolean);
            meta.textContent = bits.join(" · ");

            const aside = document.createElement("small");
            aside.textContent = item.imdb_id || "";

            button.append(title, meta, aside);
            button.addEventListener("click", () => {
                if (imdbInput) imdbInput.value = item.imdb_id || "";
                movieInput.value = item.title || movieInput.value;
                if (item.year) input("year").value = item.year;
                if (item.runtime) input("runtime").value = item.runtime;
                if (item.director) directorInput.value = item.director;
                if (Array.isArray(item.genres) && item.genres.length) {
                    genresInput.value = item.genres.join(", ");
                }
                if (Array.isArray(item.actors) && item.actors.length) {
                    actorsInput.value = item.actors.join(", ");
                }

                if (selectedMovie) {
                    selectedMovie.hidden = false;
                    selectedMovie.innerHTML =
                        `<span>IMDb</span><strong>${escapeHtml(item.title || "")}</strong>` +
                        `<small>${escapeHtml(item.imdb_id || "")}${item.year ? " · " + escapeHtml(item.year) : ""}</small>`;
                }

                closeSuggest(movieSuggestions, movieInput);
                refreshProgress();
                refreshGenreChips();
            });
            movieSuggestions.append(button);
        });

        movieSuggestions.hidden = false;
        movieInput.setAttribute("aria-expanded", "true");
    };

    const renderPeopleSuggestions = (items, container, field, role) => {
        if (!container || !field) return;
        container.replaceChildren();

        if (!items.length) {
            const empty = document.createElement("div");
            empty.className = "vanga-suggest__empty";
            empty.textContent = "Совпадений пока нет";
            container.append(empty);
            container.hidden = false;
            field.setAttribute("aria-expanded", "true");
            return;
        }

        items.forEach((item) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "vanga-suggest__item";

            const name = document.createElement("strong");
            name.textContent = item.name || "";

            const meta = document.createElement("span");
            meta.textContent =
                item.matched_from
                    ? `распознано: ${item.matched_from}`
                    : item.known_for_count
                      ? `${item.known_for_count} работ в локальной базе`
                      : role === "director" ? "режиссёр" : "актёр";

            const aside = document.createElement("small");
            aside.textContent = item.imdb_id || "";
            button.append(name, meta, aside);

            button.addEventListener("click", () => {
                if (role === "actor") {
                    const parts = field.value.split(",");
                    parts[parts.length - 1] = ` ${item.name || ""}`;
                    field.value = parts
                        .map((part) => part.trim())
                        .filter(Boolean)
                        .slice(0, 5)
                        .join(", ");
                } else {
                    field.value = item.name || "";
                }
                field.dispatchEvent(new Event("input", { bubbles: true }));
                closeSuggest(container, field);
                refreshProgress();
            });
            container.append(button);
        });

        container.hidden = false;
        field.setAttribute("aria-expanded", "true");
    };

    const fetchSearch = async (params, controller) => {
        if (!searchUrl) return [];
        const url = new URL(searchUrl, window.location.origin);
        Object.entries(params).forEach(([key, value]) => {
            if (value !== "" && value !== null && value !== undefined) {
                url.searchParams.set(key, value);
            }
        });
        const response = await fetch(url, {
            method: "GET",
            credentials: "same-origin",
            headers: { Accept: "application/json" },
            signal: controller.signal,
        });
        const data = await response.json();
        if (!response.ok || !data.ok) {
            throw new Error(data.error || "Поиск временно недоступен");
        }
        return Array.isArray(data.items) ? data.items : [];
    };

    let movieController = null;
    const searchMovie = debounce(async () => {
        const query = movieInput?.value.trim() || "";
        if (imdbInput) imdbInput.value = "";
        if (selectedMovie) selectedMovie.hidden = true;
        if (query.length < 2) {
            closeSuggest(movieSuggestions, movieInput);
            return;
        }

        movieController?.abort();
        movieController = new AbortController();
        try {
            const items = await fetchSearch(
                {
                    type: "movie",
                    q: query,
                    year: input("year")?.value || "",
                },
                movieController
            );
            renderMovieSuggestions(items);
        } catch (error) {
            if (error.name !== "AbortError") closeSuggest(movieSuggestions, movieInput);
        }
    }, 300);
    movieInput?.addEventListener("input", searchMovie);

    const personControllers = { director: null, actor: null };
    const personSearch = (field, container, role) =>
        debounce(async () => {
            if (!field) return;
            let query = field.value.trim();
            if (role === "actor") {
                query = field.value.split(",").pop().trim();
            }
            if (query.length < 2) {
                closeSuggest(container, field);
                return;
            }

            personControllers[role]?.abort();
            personControllers[role] = new AbortController();
            try {
                const items = await fetchSearch(
                    { type: "person", role, q: query },
                    personControllers[role]
                );
                renderPeopleSuggestions(items, container, field, role);
            } catch (error) {
                if (error.name !== "AbortError") closeSuggest(container, field);
            }
        }, 300);

    directorInput?.addEventListener(
        "input",
        personSearch(directorInput, directorSuggestions, "director")
    );
    actorsInput?.addEventListener(
        "input",
        personSearch(actorsInput, actorSuggestions, "actor")
    );

    document.addEventListener("pointerdown", (event) => {
        if (!event.target.closest("[data-vanga-field]")) {
            closeSuggest(movieSuggestions, movieInput);
            closeSuggest(directorSuggestions, directorInput);
            closeSuggest(actorSuggestions, actorsInput);
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") return;
        closeSuggest(movieSuggestions, movieInput);
        closeSuggest(directorSuggestions, directorInput);
        closeSuggest(actorSuggestions, actorsInput);
    });

    const readHistory = () => {
        try {
            const parsed = JSON.parse(window.localStorage.getItem(historyKey) || "[]");
            return Array.isArray(parsed) ? parsed : [];
        } catch {
            return [];
        }
    };

    const writeHistory = (items) => {
        try {
            window.localStorage.setItem(historyKey, JSON.stringify(items.slice(0, 8)));
        } catch {
            // localStorage может быть запрещён политикой браузера.
        }
    };

    const historySection = root.querySelector("[data-vanga-history]");
    const historyList = root.querySelector("[data-vanga-history-list]");

    const fillFromHistory = (item) => {
        if (!form || !item?.payload) return;
        const payload = item.payload;
        if (imdbInput) imdbInput.value = payload.imdb_id || "";
        input("title").value = payload.title || "";
        input("director").value = payload.director || "";
        input("year").value = payload.year || "";
        input("runtime").value = payload.runtime || "";
        genresInput.value = Array.isArray(payload.genres)
            ? payload.genres.join(", ")
            : payload.genres || "";
        actorsInput.value = Array.isArray(payload.actors)
            ? payload.actors.join(", ")
            : payload.actors || "";
        refreshProgress();
        refreshGenreChips();
        form.scrollIntoView({
            behavior: reducedMotion ? "auto" : "smooth",
            block: "center",
        });
    };

    const renderHistory = () => {
        if (!historySection || !historyList) return;
        const items = readHistory();
        historyList.replaceChildren();

        if (!items.length) {
            historySection.hidden = true;
            return;
        }

        historySection.hidden = false;
        items.forEach((item) => {
            const card = document.createElement("button");
            card.type = "button";
            card.className = "vanga-history__item";

            const top = document.createElement("span");
            top.textContent = item.payload?.year
                ? `${item.payload.year} · прогноз`
                : "прогноз";

            const title = document.createElement("strong");
            title.textContent = item.payload?.title || "Фильм";

            const rating = document.createElement("b");
            rating.textContent = Number(item.rating || 0).toFixed(2);

            const meta = document.createElement("small");
            const created = item.created_at ? new Date(item.created_at) : null;
            const bits = [
                item.generation ? `модель ${item.generation}` : null,
                created && !Number.isNaN(created.getTime())
                    ? created.toLocaleString("ru-RU", {
                          day: "2-digit",
                          month: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                      })
                    : null,
            ].filter(Boolean);
            meta.textContent = bits.join(" · ");

            card.append(top, title, rating, meta);
            card.addEventListener("click", () => fillFromHistory(item));
            historyList.append(card);
        });
    };

    root.querySelector("[data-vanga-history-clear]")?.addEventListener("click", () => {
        writeHistory([]);
        renderHistory();
    });

    const pushHistory = (payload, output, snapshot) => {
        const current = readHistory();
        const normalized = {
            payload,
            rating: output?.rating ?? 0,
            generation: snapshot?.generation || null,
            snapshot_id: snapshot?.id || null,
            created_at: snapshot?.created_at || new Date().toISOString(),
        };

        const key = JSON.stringify([
            payload.imdb_id || "",
            payload.title || "",
            payload.year || "",
            payload.director || "",
        ]);
        const next = [
            normalized,
            ...current.filter((item) => {
                const itemKey = JSON.stringify([
                    item.payload?.imdb_id || "",
                    item.payload?.title || "",
                    item.payload?.year || "",
                    item.payload?.director || "",
                ]);
                return itemKey !== key;
            }),
        ];
        writeHistory(next);
        renderHistory();
    };

    const renderAjaxError = (message) => {
        if (!result) return;
        result.classList.remove("has-prediction", "is-visible");
        result.innerHTML = "";
        const label = document.createElement("span");
        label.className = "vanga-result__label";
        label.textContent = "Ошибка";
        const icon = document.createElement("div");
        icon.className = "vanga-result__empty-icon is-error";
        icon.textContent = "!";
        const title = document.createElement("h2");
        title.textContent = "Прогноз не получен";
        const text = document.createElement("p");
        text.textContent = message || "Попробуйте ещё раз.";
        result.append(label, icon, title, text);
        if (analysisHost) analysisHost.replaceChildren();
    };

    if (form && predictUrl && window.fetch) {
        const submitStatus = form.querySelector("[data-vanga-submit-status]");
        let statusTimer = 0;

        form.addEventListener("submit", async (event) => {
            if (!form.checkValidity()) return;
            event.preventDefault();

            form.classList.add("is-submitting");
            const states = [
                "Собираю признаки…",
                "Сверяю историю режиссёра и актёров…",
                "Строю прогноз CatBoost…",
                "Считаю SHAP-вклады…",
            ];
            let stateIndex = 0;
            if (submitStatus) submitStatus.textContent = states[0];
            statusTimer = window.setInterval(() => {
                stateIndex = (stateIndex + 1) % states.length;
                if (submitStatus) submitStatus.textContent = states[stateIndex];
            }, 720);

            const payload = {
                imdb_id: imdbInput?.value.trim() || null,
                title: input("title").value.trim(),
                director: input("director").value.trim(),
                year: input("year").value.trim(),
                runtime: input("runtime").value.trim(),
                genres: normalizedGenres(),
                actors: (actorsInput?.value || "")
                    .split(",")
                    .map((item) => item.trim())
                    .filter(Boolean)
                    .slice(0, 5),
            };

            try {
                const csrf = form.querySelector("[data-vanga-csrf]")?.value || "";
                const response = await fetch(predictUrl, {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        Accept: "application/json",
                        "X-CSRF-Token": csrf,
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    body: JSON.stringify(payload),
                });
                const data = await response.json();
                if (!response.ok || !data.ok) {
                    throw new Error(data.error || "Не удалось получить прогноз");
                }

                result.innerHTML = data.result_html || "";
                result.classList.add("has-prediction");
                if (analysisHost) analysisHost.innerHTML = data.analysis_html || "";

                pushHistory(payload, data.output, data.snapshot);
                initDynamicContent({ scroll: true });
            } catch (error) {
                renderAjaxError(error?.message || "Сервис временно недоступен");
            } finally {
                window.clearInterval(statusTimer);
                form.classList.remove("is-submitting");
            }
        });
    }

    renderHistory();
    initDynamicContent({ scroll: false });
})();
