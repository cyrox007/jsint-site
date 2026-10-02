(function () {
    "use strict";

    var modal = document.querySelector("[data-resume-modal]");
    var openButton = document.querySelector("[data-resume-open]");
    var closeButtons = document.querySelectorAll("[data-resume-close]");
    var previousFocus = null;
    var closeTimer = null;

    function openResume() {
        if (!modal) return;
        previousFocus = document.activeElement;
        window.clearTimeout(closeTimer);
        modal.hidden = false;
        document.documentElement.classList.add("resume-modal-open");

        window.requestAnimationFrame(function () {
            modal.classList.add("is-open");
            var dialog = modal.querySelector(".resume-modal__dialog");
            if (dialog) dialog.focus();
        });
    }

    function closeResume() {
        if (!modal || modal.hidden) return;
        modal.classList.remove("is-open");
        document.documentElement.classList.remove("resume-modal-open");

        closeTimer = window.setTimeout(function () {
            modal.hidden = true;
            if (previousFocus && typeof previousFocus.focus === "function") {
                previousFocus.focus();
            }
        }, 230);
    }

    if (openButton) {
        openButton.addEventListener("click", openResume);
    }

    closeButtons.forEach(function (button) {
        button.addEventListener("click", closeResume);
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && modal && !modal.hidden) {
            closeResume();
        }
    });
})();