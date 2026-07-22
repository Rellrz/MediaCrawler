(() => {
  const STYLE_ID = "task-result-dialog-style";
  const SEEN_KEY_PREFIX = "mediacrawler_task_result_seen:";
  const NOTIFICATION_STORAGE_KEY =
    "mediacrawler_task_completion_notification";
  const NOTIFICATION_SETTING_ATTRIBUTE =
    "data-task-completion-notification-setting";
  const pageLoadedAt = Date.now();
  const observedTaskIds = new Set();
  let socket = null;
  let reconnectTimer = null;
  let activeDialog = null;
  let crawlerRunning = false;

  const OUTCOME_THEME = {
    completed: {
      accent: "#4ade80",
      border: "rgba(74, 222, 128, 0.55)",
      background: "rgba(34, 197, 94, 0.12)",
      icon: "✓",
    },
    failed: {
      accent: "#ff6b9d",
      border: "rgba(255, 0, 128, 0.55)",
      background: "rgba(255, 0, 128, 0.12)",
      icon: "×",
    },
    stopped: {
      accent: "#fbbf24",
      border: "rgba(251, 191, 36, 0.55)",
      background: "rgba(251, 191, 36, 0.12)",
      icon: "■",
    },
  };

  function translations() {
    const english = localStorage.getItem("mediacrawler_language") === "en-US";
    if (english) {
      return {
        completedTitle: "Task completed",
        completedMessage: "The crawler finished successfully.",
        failedTitle: "Task failed",
        failedMessage: "The crawler stopped because an error occurred.",
        stoppedTitle: "Task stopped",
        stoppedMessage: "Data saved before the stop is still available.",
        platform: "Platform",
        mode: "Mode",
        duration: "Duration",
        files: "Files",
        records: "Records",
        exitCode: "Exit code",
        error: "Error summary",
        unavailable: "Unavailable",
        seconds: "s",
        viewData: "View data",
        viewLogs: "View logs",
        close: "Close",
        notificationSetting: "Task completion notification",
        notificationSettingHint:
          "Send a desktop notification when the task ends",
        notificationBlocked:
          "Notifications are blocked. Enable them in browser settings.",
        notificationUnavailable:
          "Desktop notifications require HTTPS or localhost.",
      };
    }
    return {
      completedTitle: "任务已完成",
      completedMessage: "爬虫任务已正常执行完成。",
      failedTitle: "任务执行失败",
      failedMessage: "爬虫运行时发生错误，任务已结束。",
      stoppedTitle: "任务已停止",
      stoppedMessage: "停止前已经写入的数据仍然保留。",
      platform: "平台",
      mode: "模式",
      duration: "运行耗时",
      files: "数据文件",
      records: "可统计记录",
      exitCode: "退出码",
      error: "错误摘要",
      unavailable: "无法统计",
      seconds: "秒",
      viewData: "查看数据",
      viewLogs: "查看日志",
      close: "关闭",
      notificationSetting: "任务结束通知",
      notificationSettingHint: "任务结束时发送浏览器桌面通知",
      notificationBlocked: "通知权限已被阻止，请在浏览器设置中开启。",
      notificationUnavailable: "桌面通知需要使用 HTTPS 或 localhost。",
    };
  }

  function notificationsEnabled() {
    return localStorage.getItem(NOTIFICATION_STORAGE_KEY) !== "false";
  }

  function saveNotificationSetting(enabled) {
    localStorage.setItem(NOTIFICATION_STORAGE_KEY, String(enabled));
  }

  function notificationAvailabilityMessage(text) {
    if (!("Notification" in window) || !window.isSecureContext) {
      return text.notificationUnavailable;
    }
    if (Notification.permission === "denied") {
      return text.notificationBlocked;
    }
    return "";
  }

  function updateNotificationSettingState() {
    const setting = document.querySelector(
      `[${NOTIFICATION_SETTING_ATTRIBUTE}]`,
    );
    if (!setting) return;
    const checkbox = setting.querySelector("input[type='checkbox']");
    const warning = setting.querySelector("[data-notification-warning]");
    if (checkbox) {
      checkbox.checked = notificationsEnabled();
      checkbox.disabled = crawlerRunning;
    }
    if (warning) {
      warning.textContent = notificationsEnabled()
        ? notificationAvailabilityMessage(translations())
        : "";
      warning.hidden = !warning.textContent;
    }
  }

  async function requestNotificationPermission() {
    if (
      !notificationsEnabled() ||
      !("Notification" in window) ||
      !window.isSecureContext ||
      Notification.permission !== "default"
    ) {
      updateNotificationSettingState();
      return;
    }
    try {
      await Notification.requestPermission();
    } catch {
      return;
    } finally {
      updateNotificationSettingState();
    }
  }

  function notificationText(result, text) {
    const titleByOutcome = {
      completed: text.completedTitle,
      failed: text.failedTitle,
      stopped: text.stoppedTitle,
    };
    const messageByOutcome = {
      completed: text.completedMessage,
      failed: text.failedMessage,
      stopped: text.stoppedMessage,
    };
    return {
      title: `MediaCrawler · ${titleByOutcome[result.outcome]}`,
      body: `${result.platform || "-"} · ${result.crawler_type || "-"} · ${Number(
        result.duration_seconds || 0,
      ).toFixed(1)} ${text.seconds}\n${messageByOutcome[result.outcome]}`,
    };
  }

  function sendDesktopNotification(result) {
    if (
      !notificationsEnabled() ||
      !("Notification" in window) ||
      Notification.permission !== "granted" ||
      (!document.hidden && document.hasFocus())
    ) {
      return;
    }
    const message = notificationText(result, translations());
    const notification = new Notification(message.title, {
      body: message.body,
      icon: "/vite.svg",
      tag: `mediacrawler-task-${result.task_id}`,
    });
    notification.addEventListener("click", () => {
      window.focus();
      notification.close();
    });
  }

  function ensureStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      [data-task-result-overlay] {
        position: fixed;
        inset: 0;
        z-index: 1000000100;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 24px;
        background: rgba(2, 6, 23, 0.72);
        backdrop-filter: blur(7px);
        animation: task-result-fade-in 160ms ease-out;
      }
      [data-task-result-dialog] {
        --task-accent: #4ade80;
        --task-border: rgba(74, 222, 128, 0.55);
        --task-icon-bg: rgba(34, 197, 94, 0.12);
        position: relative;
        width: min(520px, 100%);
        overflow: hidden;
        border: 1px solid var(--task-border);
        border-radius: 12px;
        color: #e6edf3;
        background: linear-gradient(145deg, rgba(22, 27, 34, 0.99), rgba(13, 17, 23, 0.99));
        box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55), 0 0 32px color-mix(in srgb, var(--task-accent) 13%, transparent);
        font-family: Inter, system-ui, sans-serif;
        animation: task-result-rise-in 180ms ease-out;
      }
      [data-task-result-accent] {
        height: 3px;
        background: linear-gradient(90deg, transparent, var(--task-accent), transparent);
      }
      [data-task-result-content] { padding: 26px; }
      [data-task-result-header] { display: flex; gap: 16px; padding-right: 30px; }
      [data-task-result-icon] {
        display: inline-flex;
        flex: 0 0 46px;
        height: 46px;
        align-items: center;
        justify-content: center;
        border: 1px solid var(--task-border);
        border-radius: 50%;
        color: var(--task-accent);
        background: var(--task-icon-bg);
        font: 700 24px/1 'JetBrains Mono', monospace;
        box-shadow: 0 0 20px color-mix(in srgb, var(--task-accent) 16%, transparent);
      }
      [data-task-result-title] {
        margin: 1px 0 5px;
        color: var(--task-accent);
        font: 700 20px/1.3 'JetBrains Mono', monospace;
      }
      [data-task-result-message] { margin: 0; color: #94a3b8; font-size: 13px; line-height: 1.55; }
      [data-task-result-close] {
        position: absolute;
        top: 17px;
        right: 17px;
        width: 32px;
        height: 32px;
        border: 1px solid rgba(148, 163, 184, 0.25);
        border-radius: 50%;
        color: #94a3b8;
        background: rgba(15, 23, 42, 0.5);
        cursor: pointer;
        font: 20px/1 Arial, sans-serif;
      }
      [data-task-result-close]:hover { color: #e6edf3; border-color: rgba(148, 163, 184, 0.55); }
      [data-task-result-grid] {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
        margin-top: 22px;
      }
      [data-task-result-field] {
        min-width: 0;
        padding: 11px 12px;
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 7px;
        background: rgba(30, 41, 59, 0.38);
      }
      [data-task-result-label] { display: block; margin-bottom: 5px; color: #64748b; font: 10px 'JetBrains Mono', monospace; text-transform: uppercase; }
      [data-task-result-value] { display: block; overflow: hidden; color: #e2e8f0; font: 600 13px 'JetBrains Mono', monospace; text-overflow: ellipsis; white-space: nowrap; }
      [data-task-result-error] {
        margin-top: 10px;
        padding: 12px;
        border: 1px solid rgba(255, 0, 128, 0.28);
        border-radius: 7px;
        color: #fda4af;
        background: rgba(127, 29, 29, 0.12);
        font: 11px/1.55 'JetBrains Mono', monospace;
        overflow-wrap: anywhere;
      }
      [data-task-result-error] strong { display: block; margin-bottom: 5px; color: #fb7185; font-size: 10px; text-transform: uppercase; }
      [data-task-result-actions] { display: flex; justify-content: flex-end; gap: 10px; margin-top: 22px; }
      [data-task-result-button] {
        min-width: 108px;
        padding: 9px 15px;
        border: 1px solid rgba(148, 163, 184, 0.3);
        border-radius: 6px;
        color: #cbd5e1;
        background: rgba(30, 41, 59, 0.55);
        cursor: pointer;
        font: 600 12px 'JetBrains Mono', monospace;
      }
      [data-task-result-button='primary'] { color: #020617; border-color: var(--task-accent); background: var(--task-accent); }
      [data-task-result-button]:hover { filter: brightness(1.08); transform: translateY(-1px); }
      [data-task-result-button]:focus-visible, [data-task-result-close]:focus-visible { outline: 2px solid var(--task-accent); outline-offset: 2px; }
      [${NOTIFICATION_SETTING_ATTRIBUTE}] {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        padding: 11px 10px;
        border: 1px solid rgb(var(--cyber-border-subtle));
        border-radius: 8px;
        background: rgb(var(--cyber-bg-tertiary) / 0.3);
      }
      [${NOTIFICATION_SETTING_ATTRIBUTE}] input {
        appearance: none;
        position: relative;
        flex: 0 0 32px;
        width: 32px;
        height: 32px;
        margin: 0;
        border: 1px solid rgb(var(--cyber-border-default));
        border-radius: 5px;
        background: rgb(var(--cyber-bg-tertiary));
        cursor: pointer;
      }
      [${NOTIFICATION_SETTING_ATTRIBUTE}] input:checked {
        border-color: rgb(var(--cyber-neon-cyan));
        background: rgb(var(--cyber-neon-cyan) / 0.12);
        box-shadow: 0 0 10px rgb(var(--cyber-neon-cyan) / 0.16);
      }
      [${NOTIFICATION_SETTING_ATTRIBUTE}] input:checked::after {
        content: "✓";
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        color: rgb(var(--cyber-neon-cyan));
        font: 18px/1 'JetBrains Mono', monospace;
      }
      [${NOTIFICATION_SETTING_ATTRIBUTE}] input:focus-visible {
        outline: 2px solid rgb(var(--cyber-neon-cyan));
        outline-offset: 2px;
      }
      [${NOTIFICATION_SETTING_ATTRIBUTE}] input:disabled {
        cursor: not-allowed;
        opacity: 0.55;
      }
      [data-notification-copy] { min-width: 0; padding-top: 1px; }
      [data-notification-title] {
        color: rgb(var(--cyber-text-primary));
        font: 500 13px 'JetBrains Mono', monospace;
      }
      [data-notification-hint] {
        margin-top: 3px;
        color: rgb(var(--cyber-text-muted));
        font: 11px/1.4 'JetBrains Mono', monospace;
      }
      [data-notification-warning] {
        margin-top: 5px;
        color: rgb(var(--cyber-neon-orange));
        font: 10px/1.4 'JetBrains Mono', monospace;
      }
      @media (max-width: 540px) {
        [data-task-result-content] { padding: 22px 18px 18px; }
        [data-task-result-grid] { grid-template-columns: 1fr; }
        [data-task-result-actions] { flex-direction: column-reverse; }
        [data-task-result-button] { width: 100%; }
      }
      @keyframes task-result-fade-in { from { opacity: 0; } to { opacity: 1; } }
      @keyframes task-result-rise-in { from { opacity: 0; transform: translateY(10px) scale(.985); } to { opacity: 1; transform: none; } }
    `;
    document.head.appendChild(style);
  }

  function findButton(pattern) {
    return [...document.querySelectorAll("button")].find((button) =>
      pattern.test((button.textContent || "").trim()),
    );
  }

  function findOutputSection() {
    return [...document.querySelectorAll("section")].find((section) => {
      const headerText = section.querySelector("header")?.textContent || "";
      return /输出配置|OUTPUT_CONFIG/i.test(headerText);
    });
  }

  function injectNotificationSetting() {
    if (document.querySelector(`[${NOTIFICATION_SETTING_ATTRIBUTE}]`)) return;
    const outputSection = findOutputSection();
    const body = outputSection?.querySelector(":scope > div:last-child");
    if (!body) return;

    ensureStyles();
    const text = translations();
    const setting = document.createElement("label");
    setting.setAttribute(NOTIFICATION_SETTING_ATTRIBUTE, "");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = notificationsEnabled();
    checkbox.setAttribute("aria-label", text.notificationSetting);
    checkbox.addEventListener("change", () => {
      saveNotificationSetting(checkbox.checked);
      if (checkbox.checked) requestNotificationPermission();
      else updateNotificationSettingState();
    });

    const copy = document.createElement("span");
    copy.setAttribute("data-notification-copy", "");
    const title = document.createElement("span");
    title.setAttribute("data-notification-title", "");
    title.textContent = text.notificationSetting;
    const hint = document.createElement("div");
    hint.setAttribute("data-notification-hint", "");
    hint.textContent = text.notificationSettingHint;
    const warning = document.createElement("div");
    warning.setAttribute("data-notification-warning", "");
    copy.append(title, hint, warning);
    setting.append(checkbox, copy);
    body.appendChild(setting);
    updateNotificationSettingState();
  }

  function openDataBrowser() {
    findButton(/^(数据管理|DATA MANAGEMENT)$/i)?.click();
  }

  function focusLogs() {
    const heading = [...document.querySelectorAll("h1,h2,h3,div")].find((element) =>
      /^(系统控制台|SYSTEM CONSOLE)$/i.test((element.textContent || "").trim()),
    );
    heading?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function getDataSummary(result) {
    const startedAt = Date.parse(result.started_at || "") / 1000;
    if (!Number.isFinite(startedAt)) return null;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 4000);
    try {
      const query = result.platform
        ? `?platform=${encodeURIComponent(result.platform)}`
        : "";
      const response = await fetch(`/api/data/files${query}`, {
        signal: controller.signal,
      });
      if (!response.ok) return null;
      const files = (await response.json()).files || [];
      const taskFiles = files.filter(
        (file) => Number(file.modified_at) >= startedAt - 1,
      );
      const countableFiles = taskFiles.filter((file) =>
        Number.isFinite(Number(file.record_count)),
      );
      return {
        files: taskFiles.length,
        records: countableFiles.length
          ? countableFiles.reduce(
              (total, file) => total + Number(file.record_count),
              0,
            )
          : null,
      };
    } catch {
      return null;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  function makeField(label, value) {
    const field = document.createElement("div");
    field.setAttribute("data-task-result-field", "");
    const fieldLabel = document.createElement("span");
    fieldLabel.setAttribute("data-task-result-label", "");
    fieldLabel.textContent = label;
    const fieldValue = document.createElement("span");
    fieldValue.setAttribute("data-task-result-value", "");
    fieldValue.title = String(value);
    fieldValue.textContent = String(value);
    field.append(fieldLabel, fieldValue);
    return field;
  }

  function closeDialog() {
    if (!activeDialog) return;
    const { overlay, previousFocus } = activeDialog;
    activeDialog = null;
    overlay.remove();
    if (previousFocus instanceof HTMLElement) previousFocus.focus();
  }

  async function showDialog(result) {
    closeDialog();
    ensureStyles();
    const text = translations();
    const theme = OUTCOME_THEME[result.outcome];
    const summary = await getDataSummary(result);
    const titles = {
      completed: [text.completedTitle, text.completedMessage],
      failed: [text.failedTitle, text.failedMessage],
      stopped: [text.stoppedTitle, text.stoppedMessage],
    };
    const [titleText, messageText] = titles[result.outcome];

    const overlay = document.createElement("div");
    overlay.setAttribute("data-task-result-overlay", "");
    const dialog = document.createElement("section");
    dialog.setAttribute("data-task-result-dialog", "");
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", "task-result-title");
    dialog.style.setProperty("--task-accent", theme.accent);
    dialog.style.setProperty("--task-border", theme.border);
    dialog.style.setProperty("--task-icon-bg", theme.background);

    const accent = document.createElement("div");
    accent.setAttribute("data-task-result-accent", "");
    const content = document.createElement("div");
    content.setAttribute("data-task-result-content", "");
    const header = document.createElement("div");
    header.setAttribute("data-task-result-header", "");
    const icon = document.createElement("span");
    icon.setAttribute("data-task-result-icon", "");
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = theme.icon;
    const headingGroup = document.createElement("div");
    const title = document.createElement("h2");
    title.id = "task-result-title";
    title.setAttribute("data-task-result-title", "");
    title.textContent = titleText;
    const message = document.createElement("p");
    message.setAttribute("data-task-result-message", "");
    message.textContent = messageText;
    headingGroup.append(title, message);
    header.append(icon, headingGroup);

    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.setAttribute("data-task-result-close", "");
    closeButton.setAttribute("aria-label", text.close);
    closeButton.textContent = "×";
    closeButton.addEventListener("click", closeDialog);

    const grid = document.createElement("div");
    grid.setAttribute("data-task-result-grid", "");
    grid.append(
      makeField(text.platform, result.platform || "-"),
      makeField(text.mode, result.crawler_type || "-"),
      makeField(
        text.duration,
        `${Number(result.duration_seconds || 0).toFixed(1)} ${text.seconds}`,
      ),
      makeField(text.files, summary ? summary.files : text.unavailable),
    );
    if (summary?.records !== null && summary?.records !== undefined) {
      grid.append(makeField(text.records, summary.records));
    }
    if (result.outcome === "failed") {
      grid.append(makeField(text.exitCode, result.exit_code ?? "-"));
    }

    let errorBox = null;
    if (result.outcome === "failed" && result.error_message) {
      errorBox = document.createElement("div");
      errorBox.setAttribute("data-task-result-error", "");
      const errorLabel = document.createElement("strong");
      errorLabel.textContent = text.error;
      const errorMessage = document.createElement("span");
      errorMessage.textContent = String(result.error_message).slice(0, 360);
      errorBox.append(errorLabel, errorMessage);
    }

    const actions = document.createElement("div");
    actions.setAttribute("data-task-result-actions", "");
    const dismissButton = document.createElement("button");
    dismissButton.type = "button";
    dismissButton.setAttribute("data-task-result-button", "secondary");
    dismissButton.textContent = text.close;
    dismissButton.addEventListener("click", closeDialog);
    const primaryButton = document.createElement("button");
    primaryButton.type = "button";
    primaryButton.setAttribute("data-task-result-button", "primary");
    primaryButton.textContent =
      result.outcome === "failed" ? text.viewLogs : text.viewData;
    primaryButton.addEventListener("click", () => {
      closeDialog();
      if (result.outcome === "failed") focusLogs();
      else openDataBrowser();
    });
    actions.append(dismissButton, primaryButton);

    content.append(header, grid);
    if (errorBox) content.append(errorBox);
    content.append(actions);
    dialog.append(accent, closeButton, content);
    overlay.appendChild(dialog);
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) closeDialog();
    });

    const previousFocus = document.activeElement;
    activeDialog = { overlay, previousFocus };
    document.body.appendChild(overlay);
    closeButton.focus();
  }

  function wasSeen(taskId) {
    return sessionStorage.getItem(`${SEEN_KEY_PREFIX}${taskId}`) === "true";
  }

  function markSeen(taskId) {
    sessionStorage.setItem(`${SEEN_KEY_PREFIX}${taskId}`, "true");
  }

  function handleStatus(result) {
    if (!result?.task_id) return;
    if (result.status === "running" || result.status === "stopping") {
      crawlerRunning = true;
      updateNotificationSettingState();
      observedTaskIds.add(result.task_id);
      return;
    }
    crawlerRunning = false;
    updateNotificationSettingState();
    if (!OUTCOME_THEME[result.outcome] || wasSeen(result.task_id)) return;
    const finishedAt = Date.parse(result.finished_at || "");
    const isCurrentPageTask =
      observedTaskIds.has(result.task_id) ||
      (Number.isFinite(finishedAt) && finishedAt >= pageLoadedAt);
    if (!isCurrentPageTask) return;

    markSeen(result.task_id);
    sendDesktopNotification(result);
    showDialog(result);
  }

  document.addEventListener(
    "click",
    (event) => {
      const button = event.target.closest?.("button");
      if (
        button &&
        /^(开始爬虫|INITIATE_SCAN|START CRAWLER)$/i.test(
          (button.textContent || "").trim(),
        )
      ) {
        requestNotificationPermission();
      }
    },
    true,
  );

  const settingObserver = new MutationObserver(injectNotificationSetting);
  settingObserver.observe(document.documentElement, {
    childList: true,
    subtree: true,
  });

  function connect() {
    if (
      socket &&
      (socket.readyState === WebSocket.OPEN ||
        socket.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const connection = new WebSocket(
      `${protocol}//${window.location.host}/api/ws/status`,
    );
    socket = connection;
    connection.onmessage = (event) => {
      if (socket !== connection) return;
      try {
        handleStatus(JSON.parse(event.data));
      } catch {
        return;
      }
    };
    connection.onclose = () => {
      if (socket !== connection) return;
      socket = null;
      window.clearTimeout(reconnectTimer);
      reconnectTimer = window.setTimeout(connect, 2000);
    };
    connection.onerror = () => connection.close();
  }

  injectNotificationSetting();
  connect();
})();
