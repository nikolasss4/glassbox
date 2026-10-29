// Build a compact, text-only view of the page for the model.
//
// Interactive elements get a ref (`[e12]`) written to a data-gb-ref attribute so the
// executor can find them again. Refs are numbered in DOM order on every snapshot, which
// keeps them deterministic for a given page state (record/replay fixtures depend on it).
(maxChars) => {
  document.querySelectorAll("[data-gb-ref]").forEach((el) => el.removeAttribute("data-gb-ref"));

  const TAGS = new Set(["A", "BUTTON", "INPUT", "SELECT", "TEXTAREA", "SUMMARY"]);
  const ROLES = new Set([
    "button", "link", "checkbox", "radio", "tab", "option", "combobox", "menuitem",
    "switch", "textbox", "listbox", "slider", "searchbox",
  ]);
  const CONTROLS = "a[href],button,input,select,textarea,[role],[onclick]";
  const SKIP = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEMPLATE", "SVG", "HEAD"]);
  const vh = window.innerHeight;
  const lines = [];
  let n = 0;

  const clean = (s, max = 120) => {
    s = (s || "").replace(/\s+/g, " ").trim();
    return s.length > max ? s.slice(0, max - 1) + "…" : s;
  };
  const visible = (el) => {
    const s = getComputedStyle(el);
    if (s.display === "none" || s.visibility === "hidden" || Number(s.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const interactive = (el) =>
    (TAGS.has(el.tagName) && !(el.tagName === "A" && !el.hasAttribute("href")) &&
      !(el.tagName === "INPUT" && el.type === "hidden")) ||
    ROLES.has(el.getAttribute("role")) ||
    el.hasAttribute("onclick") ||
    el.isContentEditable;
  const roleOf = (el) => {
    const r = el.getAttribute("role");
    if (r) return r;
    if (el.tagName === "A") return "link";
    if (el.tagName === "SELECT") return "select";
    if (el.tagName === "TEXTAREA") return "textbox";
    if (el.tagName === "INPUT") {
      const t = el.type;
      if (["checkbox", "radio"].includes(t)) return t;
      if (["submit", "button", "reset"].includes(t)) return "button";
      return t === "text" ? "textbox" : t;
    }
    return el.tagName.toLowerCase();
  };
  const nameOf = (el) => {
    const label = el.getAttribute("aria-label");
    if (label) return label;
    if (el.labels && el.labels.length) return [...el.labels].map((l) => l.innerText).join(" ");
    if (["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName))
      return el.placeholder || el.title || el.name || "";
    return el.innerText || el.value || el.title || el.alt || "";
  };
  const covered = (el) => {
    const r = el.getBoundingClientRect();
    const x = r.left + Math.min(r.width / 2, 40), y = r.top + r.height / 2;
    if (y < 0 || y > vh) return false;
    const hit = document.elementFromPoint(x, y);
    return !!hit && hit !== el && !el.contains(hit) && !hit.contains(el) &&
      !(el.labels && [...el.labels].some((l) => l.contains(hit)));
  };

  const describe = (el) => {
    const ref = "e" + ++n;
    el.setAttribute("data-gb-ref", ref);
    const role = roleOf(el);
    let line = `[${ref}] ${role} "${clean(nameOf(el))}"`;
    if (el.tagName === "INPUT" && ["checkbox", "radio"].includes(el.type)) line += ` checked=${el.checked}`;
    else if (["INPUT", "TEXTAREA"].includes(el.tagName)) line += ` value="${clean(el.value, 80)}"`;
    if (el.tagName === "SELECT") {
      const opts = [...el.options].map((o) => o.text);
      line += ` selected="${clean(el.selectedOptions[0]?.text || "")}" options=[${opts.slice(0, 30).map((o) => JSON.stringify(o)).join(", ")}]`;
    }
    if (el.tagName === "A") {
      const href = el.getAttribute("href");
      if (href && href !== "#") line += ` -> ${clean(href, 80)}`;
    }
    const expanded = el.getAttribute("aria-expanded");
    if (expanded) line += ` expanded=${expanded}`;
    if (el.disabled || el.getAttribute("aria-disabled") === "true") line += " (disabled)";
    const r = el.getBoundingClientRect();
    if (r.bottom < 0) line += " (above viewport)";
    else if (r.top > vh) line += " (below viewport)";
    else if (covered(el)) line += " (covered by another element)";
    lines.push(line);
  };

  const walk = (el) => {
    if (SKIP.has(el.tagName.toUpperCase()) || !visible(el)) return;
    if (el.getAttribute("role") === "dialog" || el.getAttribute("aria-modal") === "true")
      lines.push(`[dialog "${clean(el.getAttribute("aria-label") || "")}"]`);
    if (interactive(el)) {
      describe(el);
      if (el.tagName === "SELECT") return;
      // Only descend when the element wraps other controls (e.g. a clickable card).
      if (!el.querySelector(CONTROLS)) return;
    }
    if (el.tagName === "TR") {
      const cells = [...el.children].map((c) => clean(c.innerText, 60));
      lines.push("row: " + cells.join(" | "));
      el.querySelectorAll("*").forEach((c) => { if (interactive(c) && visible(c)) describe(c); });
      return;
    }
    // A container holding only text and inline formatting (<strong>, <code>, ...) is read
    // as one line, so "use code <strong>X</strong> for 10% off" stays together.
    const inlineOnly = el.children.length > 0 && [...el.children].every((c) =>
      getComputedStyle(c).display.startsWith("inline") && !interactive(c) && !c.querySelector(CONTROLS));
    if (inlineOnly && !interactive(el)) {
      const h = /^H([1-6])$/.exec(el.tagName);
      const text = clean(el.innerText, 300);
      if (text) lines.push(h ? "#".repeat(+h[1]) + " " + text : text);
      return;
    }
    let own = "";
    for (const node of el.childNodes) if (node.nodeType === Node.TEXT_NODE) own += node.textContent;
    own = clean(own, 300);
    if (own && !interactive(el)) {
      const h = /^H([1-6])$/.exec(el.tagName);
      lines.push(h ? "#".repeat(+h[1]) + " " + own : own);
    }
    for (const child of el.children) walk(child);
  };
  walk(document.body);

  const se = document.scrollingElement || document.documentElement;
  const header = [
    `URL: ${location.href}`,
    `Title: ${document.title}`,
    `Scroll: ${Math.round(se.scrollTop)} of ${Math.max(0, se.scrollHeight - vh)}px`,
    "",
  ];
  let text = header.join("\n");
  let i = 0;
  for (; i < lines.length; i++) {
    if (text.length + lines[i].length + 1 > maxChars) break;
    text += lines[i] + "\n";
  }
  if (i < lines.length) text += `… [${lines.length - i} more lines not shown; scroll or filter to see them]\n`;
  return { text, refs: n };
}
