(async () => {
  const script = document.currentScript;
  const api = new URL(script.src).origin; // backend = wherever this file came from
  const site = script.dataset.site;

  const res = await fetch(`${api}/config?site=${encodeURIComponent(site)}`).catch(() => null);
  if (!res?.ok) return console.error("[widget] not allowed on this site, or backend offline");
  const cfg = await res.json();
  const history = [];

  const host = document.body.appendChild(document.createElement("div"));
  const root = host.attachShadow({ mode: "open" });
  root.innerHTML = `<style>
    :host{all:initial}*{box-sizing:border-box;font:14px system-ui,sans-serif}
    .fab,.panel{position:fixed;right:20px;z-index:99999}
    .fab{bottom:20px;width:56px;height:56px;border:0;border-radius:50%;color:#fff;font-size:24px;cursor:pointer}
    .panel{bottom:88px;width:min(360px,calc(100vw - 40px));height:min(500px,calc(100vh - 110px));
      display:none;flex-direction:column;background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 8px 32px #0004}
    .panel.open{display:flex}.head{padding:14px;color:#fff;font-weight:600}.fab,.head,.user,.send{background:var(--c)}
    .log{flex:1;overflow:auto;padding:12px;display:flex;flex-direction:column;gap:8px}
    .msg{max-width:85%;padding:8px 12px;border-radius:12px;white-space:pre-wrap;overflow-wrap:anywhere}
    .user{align-self:flex-end;color:#fff}.bot{align-self:flex-start;background:#f1f1f4;color:#222}
    .chip{align-self:flex-start;border:1px solid var(--c);color:var(--c);background:#fff;border-radius:16px;padding:6px 10px;cursor:pointer}
    form{display:flex;border-top:1px solid #ddd}input{flex:1;min-width:0;border:0;padding:12px}
    .send{border:0;color:#fff;padding:0 16px;cursor:pointer}
  </style>
  <button class="fab" aria-label="Chat">💬</button>
  <div class="panel"><div class="head"></div><div class="log" aria-live="polite"></div>
    <form><input placeholder="Type a message" aria-label="Message"><button class="send">Send</button></form></div>`;

  const $ = (s) => root.querySelector(s);
  host.style.setProperty("--c", cfg.color);
  $(".head").textContent = cfg.name;
  $("input").maxLength = cfg.maxChars;
  $(".fab").onclick = () => $(".panel").classList.toggle("open");

  function add(tag, cls, text) { // textContent only, so replies can't inject HTML
    const el = document.createElement(tag);
    el.className = cls;
    for (const part of text.split(/(https?:\/\/[^\s)\]]*[^\s)\].,;:!?])/)) {
      if (!/^https?:\/\//.test(part)) { el.append(part); continue; }
      const a = document.createElement("a");
      Object.assign(a, { href: part, textContent: part, target: "_blank", rel: "noopener" });
      el.append(a);
    }
    $(".log").append(el);
    $(".log").scrollTop = $(".log").scrollHeight;
    return el;
  }
  function chips(list) {
    list.forEach((t) => (add("button", "chip", t).onclick = () => send(t)));
  }
  async function send(text) {
    if (!text || $(".send").disabled) return;
    root.querySelectorAll(".chip").forEach((c) => c.remove());
    $("input").value = "";
    add("div", "msg user", text);
    $(".send").disabled = true;
    const wait = add("div", "msg bot", "…");
    try {
      const r = await fetch(`${api}/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ site, message: text, history: history.slice(-cfg.historyTurns) }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(typeof d.detail === "string" ? d.detail : "");
      wait.remove();
      add("div", "msg bot", d.reply);
      history.push({ role: "user", content: text }, { role: "assistant", content: d.reply });
      chips(d.suggestions);
    } catch (e) {
      wait.textContent = (e.constructor === Error && e.message) || "Sorry, something went wrong. Please try again.";
    }
    $(".send").disabled = false;
  }
  $("form").onsubmit = (e) => { e.preventDefault(); send($("input").value.trim()); };
  add("div", "msg bot", cfg.welcome);
  chips(cfg.suggestions);
})();
