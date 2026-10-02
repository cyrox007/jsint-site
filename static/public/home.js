(function () {
    "use strict";

    function initResumeModal() {
        var modal = document.querySelector("[data-resume-modal]");
        var openButton = document.querySelector("[data-resume-open]");
        if (!modal || !openButton) return;

        var closeButtons = modal.querySelectorAll("[data-resume-close]");
        var dialog = modal.querySelector(".resume-modal__dialog");
        var lastFocused = null;

        function openModal() {
            lastFocused = document.activeElement;
            modal.setAttribute("aria-hidden", "false");
            modal.classList.add("is-open");
            document.documentElement.classList.add("resume-modal-open");

            window.requestAnimationFrame(function () {
                var close = modal.querySelector(".resume-modal__close");
                if (close) close.focus();
            });
        }

        function closeModal() {
            modal.classList.remove("is-open");
            modal.setAttribute("aria-hidden", "true");
            document.documentElement.classList.remove("resume-modal-open");

            if (lastFocused && typeof lastFocused.focus === "function") {
                lastFocused.focus();
            }
        }

        openButton.addEventListener("click", openModal);
        closeButtons.forEach(function (button) {
            button.addEventListener("click", closeModal);
        });

        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && modal.classList.contains("is-open")) {
                closeModal();
            }
        });

        modal.addEventListener("keydown", function (event) {
            if (event.key !== "Tab" || !dialog) return;

            var focusable = dialog.querySelectorAll(
                'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])'
            );
            if (!focusable.length) return;

            var first = focusable[0];
            var last = focusable[focusable.length - 1];

            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initResumeModal);
    } else {
        initResumeModal();
    }
})();