const DEFAULT_LOADING_TITLE = "Выполняем запрос…";
const DEFAULT_LOADING_SUBTITLE = "Обычно это занимает несколько секунд";

const getOverlay = () => document.getElementById("loading-overlay");

const showOverlay = (title, subtitle) => {
    const overlay = getOverlay();
    if (!overlay) return;
    const titleEl = document.getElementById("loading-title");
    const subtitleEl = document.getElementById("loading-subtitle");
    if (titleEl) titleEl.textContent = title || DEFAULT_LOADING_TITLE;
    if (subtitleEl) subtitleEl.textContent = subtitle || DEFAULT_LOADING_SUBTITLE;
    overlay.classList.add("is-active");
    overlay.setAttribute("aria-hidden", "false");
};

const hideOverlay = () => {
    const overlay = getOverlay();
    if (!overlay) return;
    overlay.classList.remove("is-active");
    overlay.setAttribute("aria-hidden", "true");
};

const findLoadingMeta = (element) => {
    let current = element;
    while (current && current !== document.body) {
        if (current.dataset && current.dataset.loadingTitle) {
            return {
                title: current.dataset.loadingTitle,
                subtitle: current.dataset.loadingSubtitle || "",
            };
        }
        current = current.parentElement;
    }
    return { title: "", subtitle: "" };
};

const setupComposer = () => {
    const textarea = document.getElementById("message-text");
    const fileInput = document.getElementById("data-file");
    const filePill = document.getElementById("selected-file-pill");
    const thread = document.getElementById("chat-thread");

    if (textarea) {
        const resize = () => {
            textarea.style.height = "auto";
            textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
        };

        resize();
        textarea.addEventListener("input", resize);

        document.querySelectorAll("[data-prompt]").forEach((button) => {
            button.addEventListener("click", () => {
                textarea.value = button.dataset.prompt || "";
                textarea.focus();
                resize();
            });
        });
    }

    if (fileInput && filePill) {
        const syncFilePill = () => {
            const file = fileInput.files?.[0];
            if (!file) {
                filePill.hidden = true;
                filePill.textContent = "";
                return;
            }
            filePill.hidden = false;
            filePill.textContent = `Выбрано: ${file.name}`;
        };

        fileInput.addEventListener("change", syncFilePill);
        syncFilePill();
    }

    if (thread) {
        thread.scrollTop = thread.scrollHeight;
    }
};

const setupDropzoneAutoSubmit = () => {
    const dropzoneInput = document.querySelector(".dropzone input[type='file']");
    if (!dropzoneInput) return;
    const form = dropzoneInput.closest("form");
    if (!form) return;
    dropzoneInput.addEventListener("change", () => {
        if (dropzoneInput.files && dropzoneInput.files.length > 0) {
            if (typeof form.requestSubmit === "function") {
                form.requestSubmit();
            } else {
                form.submit();
            }
        }
    });
};

document.addEventListener("DOMContentLoaded", () => {
    setupComposer();
    setupDropzoneAutoSubmit();

    document.body.addEventListener("htmx:beforeRequest", (event) => {
        const meta = findLoadingMeta(event.target);
        showOverlay(meta.title, meta.subtitle);
    });
    document.body.addEventListener("htmx:afterRequest", hideOverlay);
    document.body.addEventListener("htmx:responseError", hideOverlay);
    document.body.addEventListener("htmx:sendError", hideOverlay);
    document.body.addEventListener("htmx:afterSwap", () => {
        hideOverlay();
        setupComposer();
        setupDropzoneAutoSubmit();
    });
});
