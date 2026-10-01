(function () {
    "use strict";

    function slugify(value, index) {
        var slug = String(value || "")
            .trim()
            .toLowerCase()
            .replace(/[^a-zа-яё0-9]+/gi, "-")
            .replace(/^-+|-+$/g, "");
        return slug || ("section-" + index);
    }

    function buildToc() {
        var content = document.getElementById("article-content");
        var toc = document.getElementById("article-toc");
        if (!content || !toc) return;

        var headings = Array.prototype.slice.call(
            content.querySelectorAll("h2, h3")
        );
        if (!headings.length) return;

        toc.innerHTML = "";
        headings.forEach(function (heading, index) {
            if (!heading.id) {
                heading.id = "article-" + slugify(heading.textContent, index + 1);
            }

            var link = document.createElement("a");
            link.href = "#" + heading.id;
            link.textContent = heading.textContent || ("Раздел " + (index + 1));
            link.className = "portfolio-toc__link";
            if (heading.tagName === "H3") {
                link.classList.add("portfolio-toc__link--nested");
            }
            toc.appendChild(link);
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", buildToc);
    } else {
        buildToc();
    }
})();