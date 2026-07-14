(() => {
  const DELETE_BUTTON_ATTRIBUTE = "data-file-delete-button";

  function translations() {
    const isEnglish = localStorage.getItem("mediacrawler_language") === "en-US";
    return isEnglish
      ? {
          deleteLabel: "DELETE",
          deletingLabel: "DELETING...",
          confirm: (name) => `Permanently delete ${name}? This cannot be undone.`,
          success: "File deleted",
          missing: "Unable to identify this file. Rescan and try again.",
          duplicate: "Multiple files share this name. Rename the file before deleting it.",
          failed: "Failed to delete file",
        }
      : {
          deleteLabel: "删除",
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
    button.textContent = text.deletingLabel;
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
      button.textContent = text.deleteLabel;
    }
  }

  function addDeleteButtons() {
    const text = translations();
    document.querySelectorAll(".card-scan").forEach((card) => {
      if (card.querySelector(`[${DELETE_BUTTON_ATTRIBUTE}]`)) return;
      const actionBar = [...card.querySelectorAll("div")].find((element) => {
        const classes = element.classList;
        return classes.contains("flex") &&
          classes.contains("gap-1") &&
          classes.contains("opacity-0");
      });
      if (!actionBar) return;

      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute(DELETE_BUTTON_ATTRIBUTE, "");
      button.className = [
        "inline-flex items-center justify-center rounded-md",
        "h-7 px-2 font-mono text-xs",
        "text-cyber-neon-pink hover:text-cyber-neon-pink",
        "hover:bg-cyber-neon-pink/10 disabled:opacity-50",
      ].join(" ");
      button.textContent = text.deleteLabel;
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        deleteFile(card, button);
      });
      actionBar.appendChild(button);
    });
  }

  const observer = new MutationObserver(addDeleteButtons);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  addDeleteButtons();
})();
