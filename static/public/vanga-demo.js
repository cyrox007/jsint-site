(() => {
    const root = document.querySelector("[data-vanga-demo]");
    if (!root) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const reveal = (element) => element.classList.add("is-visible");
    const revealTargets = [...root.querySelectorAll("[data-vanga-reveal]")];

    if (reducedMotion || !("IntersectionObserver" in window)) {
        revealTargets.forEach(reveal);
    } else {
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (!entry.isIntersecting) return;
                    reveal(entry.target);
                    observer.unobserve(entry.target);
                });
            },
            { threshold: 0.14 }
        );
        revealTargets.forEach((item) => observer.observe(item));
    }

    root.querySelectorAll(".vanga-card").forEach((card) => {
        if (reducedMotion) return;
        card.addEventListener("pointermove", (event) => {
            const rect = card.getBoundingClientRect();
            const x = ((event.clientX - rect.left) / rect.width) * 100;
            const y = ((event.clientY - rect.top) / rect.height) * 100;
            card.style.setProperty("--mx", `${x}%`);
            card.style.setProperty("--my", `${y}%`);
        });
    });

    const form = root.querySelector("[data-vanga-form]");
    if (form) {
        const requiredInputs = [...form.querySelectorAll("input[required]")];
        const progress = form.querySelector("[data-vanga-form-progress]");
        const submitStatus = form.querySelector("[data-vanga-submit-status]");

        const refreshProgress = () => {
            const completed = requiredInputs.filter((input) => input.value.trim()).length;
            const value = requiredInputs.length
                ? Math.round((completed / requiredInputs.length) * 100)
                : 0;
            if (progress) progress.style.width = `${value}%`;
        };

        requiredInputs.forEach((input) => {
            input.addEventListener("input", refreshProgress);
            input.addEventListener("change", refreshProgress);
        });
        refreshProgress();

        form.addEventListener("submit", () => {
            if (!form.checkValidity()) return;

            form.classList.add("is-submitting");
            const states = [
                "Собираю признаки…",
                "Сверяю историю режиссёра и актёров…",
                "Строю прогноз CatBoost…",
                "Считаю SHAP-вклады…",
            ];
            let index = 0;
            if (submitStatus) {
                submitStatus.textContent = states[0];
                window.setInterval(() => {
                    index = (index + 1) % states.length;
                    submitStatus.textContent = states[index];
                }, 720);
            }
        });
    }

    const result = root.querySelector("[data-vanga-result]");
    const ratingNode = root.querySelector("[data-rating-value]");
    const ratingRing = root.querySelector("[data-rating-ring]");

    if (result && result.classList.contains("has-prediction")) {
        window.requestAnimationFrame(() => result.classList.add("is-visible"));

        const rating = Number(ratingNode?.dataset.rating || ratingRing?.dataset.rating || 0);
        if (ratingRing) {
            const angle = Math.max(0, Math.min(10, rating)) * 36;
            window.requestAnimationFrame(() => {
                ratingRing.style.setProperty("--rating-angle", `${angle}deg`);
            });
        }

        if (ratingNode) {
            if (reducedMotion) {
                ratingNode.textContent = rating.toFixed(2);
            } else {
                const duration = 950;
                const start = performance.now();
                const animateRating = (now) => {
                    const progress = Math.min(1, (now - start) / duration);
                    const eased = 1 - Math.pow(1 - progress, 3);
                    ratingNode.textContent = (rating * eased).toFixed(2);
                    if (progress < 1) {
                        window.requestAnimationFrame(animateRating);
                    }
                };
                window.requestAnimationFrame(animateRating);
            }
        }

        root.querySelectorAll("[data-vanga-impact]").forEach((item) => {
            const strength = Math.max(0, Math.min(100, Number(item.dataset.strength || 0)));
            const bar = item.querySelector(".vanga-impact__track i");
            if (!bar) return;
            window.requestAnimationFrame(() => {
                bar.style.width = `${strength}%`;
            });
        });

        if (!reducedMotion) {
            window.setTimeout(() => {
                result.scrollIntoView({ behavior: "smooth", block: "center" });
            }, 180);
        }
    }

    const factors = [...root.querySelectorAll("[data-vanga-factor]")];
    const showFactor = (item, index = 0) => {
        const strength = Math.max(0, Math.min(100, Number(item.dataset.strength || 0)));
        const bar = item.querySelector(".vanga-factor-card__impact i");
        const delay = reducedMotion ? 0 : Math.min(index * 35, 280);

        window.setTimeout(() => {
            item.classList.add("is-visible");
            if (bar) bar.style.width = `${strength}%`;
        }, delay);
    };

    if (factors.length) {
        if (reducedMotion || !("IntersectionObserver" in window)) {
            factors.forEach(showFactor);
        } else {
            const factorObserver = new IntersectionObserver(
                (entries) => {
                    const visible = entries.filter((entry) => entry.isIntersecting);
                    visible.forEach((entry, index) => {
                        showFactor(entry.target, index);
                        factorObserver.unobserve(entry.target);
                    });
                },
                { threshold: 0.12 }
            );
            factors.forEach((item) => factorObserver.observe(item));
        }
    }
})();
