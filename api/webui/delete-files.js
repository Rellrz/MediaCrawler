(() => {
  const DELETE_BUTTON_ATTRIBUTE = "data-file-delete-button";
  const RENAME_BOUND_ATTRIBUTE = "data-file-rename-bound";
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
      h3[${RENAME_BOUND_ATTRIBUTE}] {
        cursor: text;
      }
      h3[${RENAME_BOUND_ATTRIBUTE}]:hover {
        color: #00d4ff;
        text-decoration: underline;
        text-underline-offset: 3px;
      }
      [data-file-rename-input] {
        width: 100%;
        min-width: 0;
        padding: 4px 7px;
        border: 1px solid #00d4ff;
        border-radius: 4px;
        color: inherit;
        background: rgba(13, 17, 23, 0.92);
        font: inherit;
        outline: none;
      }
      [data-file-rename-editor] {
        display: flex;
        min-width: 0;
        flex-direction: column;
        gap: 4px;
      }
      [data-file-rename-hint] {
        color: #94a3b8;
        font: 11px/1.3 'JetBrains Mono', monospace;
        white-space: normal;
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
          renameLabel: "Click to rename",
          renameEmpty: "File name cannot be empty",
          renameMissing: "Unable to identify this file. Rescan and try again.",
          renameDuplicate: "Multiple files share this name. Rescan and try again.",
          renameFailed: "Failed to rename file",
          renameSuccess: "File renamed",
          renameHint: "Edit the name, then click anywhere to save",
        }
      : {
          deleteLabel: "删除文件",
          deletingLabel: "删除中...",
          confirm: (name) => `确定永久删除“${name}”吗？删除后无法恢复。`,
          success: "文件已删除",
          missing: "无法识别该文件，请重新扫描后再试。",
          duplicate: "存在多个同名文件，请重命名后再删除。",
          failed: "文件删除失败",
          renameLabel: "点击重命名",
          renameEmpty: "文件名不能为空",
          renameMissing: "无法识别该文件，请重新扫描后再试。",
          renameDuplicate: "存在多个同名文件，请重新扫描后再试。",
          renameFailed: "文件重命名失败",
          renameSuccess: "文件已重命名",
          renameHint: "修改名称后，点击任意位置保存",
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

  async function renameFile(fileName, newName) {
    const text = translations();
    const filesResponse = await fetch("/api/data/files");
    if (!filesResponse.ok) throw new Error(`HTTP ${filesResponse.status}`);
    const files = (await filesResponse.json()).files || [];
    const matches = files.filter((file) => file.name === fileName);
    if (matches.length === 0) throw new Error(text.renameMissing);
    if (matches.length > 1) throw new Error(text.renameDuplicate);

    const response = await fetch(`/api/data/files/${encodedPath(matches[0].path)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_name: newName }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${response.status}`);
    }
  }

  function enableFileNameRename(card) {
    const heading = card.querySelector("h3[title]");
    if (!heading || heading.hasAttribute(RENAME_BOUND_ATTRIBUTE)) return;

    const text = translations();
    heading.setAttribute(RENAME_BOUND_ATTRIBUTE, "");
    heading.setAttribute("aria-label", `${text.renameLabel}: ${heading.title}`);

    const startEditing = (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (heading.querySelector("input")) return;

      const fileName = heading.getAttribute("title");
      const extensionIndex = fileName.lastIndexOf(".");
      const originalName = extensionIndex > 0 ? fileName.slice(0, extensionIndex) : fileName;
      const originalContent = heading.textContent;
      const input = document.createElement("input");
      input.type = "text";
      input.value = originalName;
      input.setAttribute("data-file-rename-input", "");
      input.setAttribute("aria-label", text.renameLabel);

      let saving = false;
      const restore = () => {
        heading.textContent = originalContent;
      };
      const submit = async () => {
        if (saving) return;
        const newName = input.value;
        if (newName === originalName) {
          restore();
          return;
        }
        if (!newName.trim()) {
          showToast(text.renameEmpty, true);
          restore();
          return;
        }

        saving = true;
        input.disabled = true;
        try {
          await renameFile(fileName, newName);
          showToast(text.renameSuccess);
          findRescanButton()?.click();
        } catch (error) {
          showToast(`${text.renameFailed}: ${error.message}`, true);
          restore();
        }
      };

      input.addEventListener("click", (inputEvent) => inputEvent.stopPropagation());
      input.addEventListener("blur", submit, { once: true });

      const editor = document.createElement("span");
      editor.setAttribute("data-file-rename-editor", "");
      const hint = document.createElement("span");
      hint.setAttribute("data-file-rename-hint", "");
      hint.textContent = text.renameHint;
      editor.append(input, hint);

      heading.textContent = "";
      heading.appendChild(editor);
      input.focus();
      input.select();
    };

    heading.addEventListener("click", startEditing);
  }

  function enhanceFileCards() {
    ensureDeleteButtonStyles();
    const text = translations();
    document.querySelectorAll(".card-scan").forEach((card) => {
      enableFileNameRename(card);
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

  const observer = new MutationObserver(enhanceFileCards);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  enhanceFileCards();
})();
