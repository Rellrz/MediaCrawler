(() => {
  const STORAGE_KEY = "mediacrawler_crawl_speed";
  const PANEL_ATTRIBUTE = "data-crawl-speed-panel";
  const DEFAULTS = {
    comment_interval_min: 0,
    comment_interval_max: 0,
    page_interval_min: 2,
    page_interval_max: 5,
    periodic_pause_page_count: 5,
    periodic_pause_min: 20,
    periodic_pause_max: 40,
  };

  function copyDefaults() {
    return { ...DEFAULTS };
  }

  function loadSettings() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
      return Object.fromEntries(
        Object.entries(DEFAULTS).map(([key, fallback]) => {
          const value = Number(saved[key]);
          return [key, Number.isFinite(value) && value >= 0 ? value : fallback];
        }),
      );
    } catch {
      return copyDefaults();
    }
  }

  let settings = loadSettings();

  function saveSettings() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  }

  function isEnglish() {
    return localStorage.getItem("mediacrawler_language") === "en-US";
  }

  function text() {
    return isEnglish()
      ? {
          title: "CRAWL SPEED",
          description: "Random delays for comment pagination",
          comment: "Per comment (seconds)",
          page: "Per page (seconds)",
          every: "Pages per long pause",
          pages: "Pages",
          periodic: "Long pause (seconds)",
          min: "Min",
          max: "Max",
        }
      : {
          title: "爬取速度",
          description: "评论分页随机间隔配置",
          comment: "每条评论间隔（秒）",
          page: "每页完成间隔（秒）",
          every: "周期休息页数",
          pages: "页数",
          periodic: "周期休息时间（秒）",
          min: "最小",
          max: "最大",
        };
  }

  function ensureStyles() {
    if (document.getElementById("crawl-speed-styles")) return;
    const style = document.createElement("style");
    style.id = "crawl-speed-styles";
    style.textContent = `
      [${PANEL_ATTRIBUTE}] {
        padding-top: 14px;
        border-top: 1px solid rgb(var(--cyber-border-subtle) / 0.5);
      }
      [${PANEL_ATTRIBUTE}] .crawl-speed-heading {
        margin-bottom: 12px;
      }
      [${PANEL_ATTRIBUTE}] .crawl-speed-title {
        color: rgb(var(--cyber-neon-cyan));
        font: 600 13px 'JetBrains Mono', monospace;
      }
      [${PANEL_ATTRIBUTE}] .crawl-speed-description {
        margin-top: 2px;
        color: rgb(var(--cyber-text-muted));
        font: 11px 'JetBrains Mono', monospace;
      }
      [${PANEL_ATTRIBUTE}] .crawl-speed-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px;
      }
      [${PANEL_ATTRIBUTE}] .crawl-speed-field {
        min-width: 0;
      }
      [${PANEL_ATTRIBUTE}] .crawl-speed-field-wide {
        grid-column: 1 / -1;
      }
      [${PANEL_ATTRIBUTE}] label {
        display: block;
        margin-bottom: 6px;
        color: rgb(var(--cyber-text-secondary));
        font: 11px 'JetBrains Mono', monospace;
      }
      [${PANEL_ATTRIBUTE}] .crawl-speed-pair {
        display: grid;
        grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
        gap: 8px;
      }
      [${PANEL_ATTRIBUTE}] .crawl-speed-input-wrap {
        position: relative;
      }
      [${PANEL_ATTRIBUTE}] input {
        box-sizing: border-box;
        width: 100%;
        height: 34px;
        padding: 7px 8px 7px 42px;
        border: 1px solid rgb(var(--cyber-border-default));
        border-radius: 6px;
        color: rgb(var(--cyber-text-primary));
        background: rgb(var(--cyber-bg-tertiary));
        font: 12px 'JetBrains Mono', monospace;
        outline: none;
      }
      [${PANEL_ATTRIBUTE}] input:focus {
        border-color: rgb(var(--cyber-neon-cyan));
        box-shadow: 0 0 10px rgb(var(--cyber-neon-cyan) / 0.2);
      }
      [${PANEL_ATTRIBUTE}] .crawl-speed-prefix {
        position: absolute;
        top: 50%;
        left: 8px;
        transform: translateY(-50%);
        color: rgb(var(--cyber-text-muted));
        font: 10px 'JetBrains Mono', monospace;
        pointer-events: none;
      }
      @media (max-width: 1100px) {
        [${PANEL_ATTRIBUTE}] .crawl-speed-grid { grid-template-columns: 1fr; }
        [${PANEL_ATTRIBUTE}] .crawl-speed-field-wide { grid-column: auto; }
      }
    `;
    document.head.appendChild(style);
  }

  function pairField(label, minimumKey, maximumKey, translations) {
    const field = document.createElement("div");
    field.className = "crawl-speed-field crawl-speed-field-wide";
    const fieldLabel = document.createElement("label");
    fieldLabel.textContent = label;
    field.append(fieldLabel);

    const pair = document.createElement("div");
    pair.className = "crawl-speed-pair";
    pair.append(
      numberInput(minimumKey, translations.min, 0.1),
      numberInput(maximumKey, translations.max, 0.1),
    );
    field.append(pair);
    return field;
  }

  function numberInput(key, prefix, step) {
    const wrapper = document.createElement("div");
    wrapper.className = "crawl-speed-input-wrap";
    const prefixElement = document.createElement("span");
    prefixElement.className = "crawl-speed-prefix";
    prefixElement.textContent = prefix;

    const input = document.createElement("input");
    input.type = "number";
    input.min = key === "periodic_pause_page_count" ? "1" : "0";
    input.step = String(step);
    input.value = String(settings[key]);
    input.dataset.speedKey = key;
    input.setAttribute("aria-label", key);
    input.addEventListener("input", () => {
      const value = Number(input.value);
      if (!Number.isFinite(value) || value < Number(input.min)) return;
      settings[key] = value;
      saveSettings();
    });

    wrapper.append(prefixElement, input);
    return wrapper;
  }

  function findAuthSection() {
    return [...document.querySelectorAll("section")].find((section) => {
      const headerText = section.querySelector("header")?.textContent || "";
      return /登录配置|AUTH|LOGIN CONFIG/i.test(headerText);
    });
  }

  function injectPanel() {
    if (document.querySelector(`[${PANEL_ATTRIBUTE}]`)) return;
    const authSection = findAuthSection();
    const body = authSection?.querySelector(":scope > div:last-child");
    if (!body) return;

    ensureStyles();
    const translations = text();
    const panel = document.createElement("div");
    panel.setAttribute(PANEL_ATTRIBUTE, "");
    const heading = document.createElement("div");
    heading.className = "crawl-speed-heading";
    const title = document.createElement("div");
    title.className = "crawl-speed-title";
    title.textContent = translations.title;
    const description = document.createElement("div");
    description.className = "crawl-speed-description";
    description.textContent = translations.description;
    heading.append(title, description);

    const grid = document.createElement("div");
    grid.className = "crawl-speed-grid";
    grid.append(
      pairField(
        translations.comment,
        "comment_interval_min",
        "comment_interval_max",
        translations,
      ),
      pairField(
        translations.page,
        "page_interval_min",
        "page_interval_max",
        translations,
      ),
    );

    const periodicField = document.createElement("div");
    periodicField.className = "crawl-speed-field";
    const periodicLabel = document.createElement("label");
    periodicLabel.textContent = translations.every;
    periodicField.append(
      periodicLabel,
      numberInput("periodic_pause_page_count", translations.pages, 1),
    );
    grid.append(periodicField);

    const pauseField = pairField(
      translations.periodic,
      "periodic_pause_min",
      "periodic_pause_max",
      translations,
    );
    pauseField.classList.remove("crawl-speed-field-wide");
    grid.append(pauseField);

    panel.append(heading, grid);
    body.append(panel);
  }

  function patchCrawlerRequest() {
    const originalOpen = XMLHttpRequest.prototype.open;
    const originalSend = XMLHttpRequest.prototype.send;

    XMLHttpRequest.prototype.open = function (method, url, ...args) {
      this.__crawlSpeedMethod = method;
      this.__crawlSpeedUrl = String(url);
      return originalOpen.call(this, method, url, ...args);
    };

    XMLHttpRequest.prototype.send = function (body) {
      if (
        String(this.__crawlSpeedMethod).toUpperCase() === "POST" &&
        this.__crawlSpeedUrl.includes("/api/crawler/start") &&
        typeof body === "string"
      ) {
        try {
          const payload = JSON.parse(body);
          body = JSON.stringify({ ...payload, ...settings });
        } catch {
          // Let the original request report malformed JSON.
        }
      }
      return originalSend.call(this, body);
    };
  }

  patchCrawlerRequest();
  injectPanel();
  new MutationObserver(injectPanel).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
})();
