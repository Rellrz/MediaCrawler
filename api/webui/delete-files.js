(() => {
  const DELETE_BUTTON_ATTRIBUTE = "data-file-delete-button";
  const DELETE_BUTTON_STYLE_ID = "file-delete-button-style";

  function ensureDeleteButtonStyles() {
    if (document.getElementById(DELETE_BUTTON_STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = DELETE_BUTTON_STYLE_ID;
    style.textContent = `
      [${DELETE_BUTTON_ATTRIBUTE}] {
        position: absolute;
        top: 8px;
        right: 8px;
        z-index: 20;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        padding: 0;
        border: 1px solid rgba(239, 68, 68, 0.45);
        border-radius: 9999px;
        color: #ef4444;
        background: rgba(239, 68, 68, 0.08);
        font: 22px/1 Arial, sans-serif;
        cursor: pointer;
        transition: color 150ms, background 150ms, border-color 150ms,
          transform 150ms;
      }
      [${DELETE_BUTTON_ATTRIBUTE}]:hover {
        color: #f87171;
        border-color: rgba(248, 113, 113, 0.8);
        background: rgba(239, 68, 68, 0.18);
        transform: scale(1.06);
      }
      [${DELETE_BUTTON_ATTRIBUTE}]:focus-visible {
        outline: 2px solid rgba(248, 113, 113, 0.9);
        outline-offset: 2px;
      }
      [${DELETE_BUTTON_ATTRIBUTE}]:disabled {
        cursor: wait;
        opacity: 0.55;
        transform: none;
      }
    `;
    document.head.appendChild(style);
  }

  function translations() {
    const isEnglish = localStorage.getItem("mediacrawler_language") === "en-US";
    return isEnglish
      ? {
          deleteLabel: "Delete file",
          deletingLabel: "DELETING...",
          confirm: (name) => `Permanently delete ${name}? This cannot be undone.`,
          success: "File deleted",
          missing: "Unable to identify this file. Rescan and try again.",
          duplicate: "Multiple files share this name. Rename the file before deleting it.",
          failed: "Failed to delete file",
        }
      : {
          deleteLabel: "删除文件",
          deletingLabel: "删除中...",
          confirm: (name) => `确定永久删除“${name}”吗？删除后无法恢复。`,
          success: "文件已删除",
          missing: "无法识别该文件，请重新扫描后再试。",
          duplicate: "存在多个同名文件，请重命名后再删除。",
          failed: "文件删除失败",
        };
  }

  function showToast(message, isError = false) {
    const toast = document.createElement("div");
    toast.textContent = message;
    toast.setAttribute("role", "status");
    toast.style.cssText = [
      "position:fixed",
      "right:24px",
      "top:24px",
      "z-index:1000000000",
      "max-width:420px",
      "padding:12px 16px",
      "border-radius:6px",
      "font:13px 'JetBrains Mono',monospace",
      `color:${isError ? "#ff6b9d" : "#4ade80"}`,
      `border:1px solid ${isError ? "#ff0080" : "#22c55e"}`,
      "background:#0d1117",
      "box-shadow:0 8px 24px rgba(0,0,0,.35)",
    ].join(";");
    document.body.appendChild(toast);
    window.setTimeout(() => toast.remove(), 3000);
  }

  function encodedPath(path) {
    return path.split("/").map(encodeURIComponent).join("/");
  }

  function findRescanButton() {
    return [...document.querySelectorAll("button")].find((button) =>
      /重新扫描|RESCAN/i.test(button.textContent || ""),
    );
  }

  async function deleteFile(card, button) {
    const text = translations();
    const fileName = card.querySelector("h3[title]")?.getAttribute("title");
    if (!fileName) {
      showToast(text.missing, true);
      return;
    }
    if (!window.confirm(text.confirm(fileName))) return;

    button.disabled = true;
    button.textContent = "…";
    button.setAttribute("aria-label", text.deletingLabel);
    try {
      const filesResponse = await fetch("/api/data/files");
      if (!filesResponse.ok) throw new Error(`HTTP ${filesResponse.status}`);
      const files = (await filesResponse.json()).files || [];
      const matches = files.filter((file) => file.name === fileName);
      if (matches.length === 0) throw new Error(text.missing);
      if (matches.length > 1) throw new Error(text.duplicate);

      const deleteResponse = await fetch(
        `/api/data/files/${encodedPath(matches[0].path)}`,
        { method: "DELETE" },
      );
      if (!deleteResponse.ok) {
        const body = await deleteResponse.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${deleteResponse.status}`);
      }

      showToast(text.success);
      findRescanButton()?.click();
    } catch (error) {
      showToast(`${text.failed}: ${error.message}`, true);
      button.disabled = false;
      button.textContent = "×";
      button.setAttribute("aria-label", text.deleteLabel);
    }
  }

  function addDeleteButtons() {
    ensureDeleteButtonStyles();
    const text = translations();
    document.querySelectorAll(".card-scan").forEach((card) => {
      if (card.querySelector(`[${DELETE_BUTTON_ATTRIBUTE}]`)) return;

      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute(DELETE_BUTTON_ATTRIBUTE, "");
      button.setAttribute("aria-label", text.deleteLabel);
      button.title = text.deleteLabel;
      button.textContent = "×";
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        deleteFile(card, button);
      });
      card.appendChild(button);
    });
  }

  const observer = new MutationObserver(addDeleteButtons);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  addDeleteButtons();
})();
