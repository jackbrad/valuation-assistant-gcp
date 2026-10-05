/* @ds-bundle: {"format":4,"namespace":"Clearline","components":[{"name":"TopBar"},{"name":"Button"},{"name":"TextField"},{"name":"PromptBox"},{"name":"Tabs"},{"name":"Switch"},{"name":"Card"},{"name":"Metric"},{"name":"Table"},{"name":"Badge"},{"name":"Banner"},{"name":"Icon"}]} */
(function () {
  var React = window.React;
  var h = React.createElement;
  function cx() { return Array.prototype.filter.call(arguments, Boolean).join(" "); }
  function omit(o, keys) { var r = {}; for (var k in o) if (keys.indexOf(k) < 0) r[k] = o[k]; return r; }

  function Icon(p) {
    return h("span", Object.assign({ className: cx("cl-icon", p.className), "aria-hidden": p.label ? undefined : "true", role: p.label ? "img" : undefined, "aria-label": p.label, style: p.size ? { fontSize: p.size } : undefined }), p.name);
  }

  function Button(p) {
    var variant = p.variant || "primary", size = p.size || "md";
    var rest = omit(p, ["variant", "size", "icon", "iconEnd", "className", "children"]);
    return h("button", Object.assign({ type: "button" }, rest, { className: cx("cl-btn", "cl-btn-" + variant, size !== "md" && "cl-btn-" + size, p.className) }),
      p.icon ? h(Icon, { name: p.icon }) : null, p.children, p.iconEnd ? h(Icon, { name: p.iconEnd }) : null);
  }

  var fid = 0;
  function TextField(p) {
    var idRef = React.useRef(null); if (!idRef.current) idRef.current = p.id || "cl-f-" + (++fid);
    var id = idRef.current;
    var rest = omit(p, ["label", "help", "error", "icon", "className", "id"]);
    var msg = p.error || p.help;
    return h("div", { className: cx("cl-field", p.error && "cl-field-error", p.className) },
      p.label ? h("label", { className: "cl-field-label", htmlFor: id }, p.label) : null,
      h("div", { className: "cl-input-wrap" }, p.icon ? h(Icon, { name: p.icon }) : null,
        h("input", Object.assign({ className: "cl-input", id: id, "aria-invalid": p.error ? "true" : undefined, "aria-describedby": msg ? id + "-m" : undefined }, rest))),
      msg ? h("div", { className: "cl-field-help", id: id + "-m" }, p.error ? h(Icon, { name: "error", size: 14 }) : null, p.error ? " " : null, msg) : null);
  }

  function PromptBox(p) {
    var st = React.useState(p.defaultValue || ""), v = st[0], setV = st[1];
    function send() { if (v.trim() && p.onSubmit) { p.onSubmit(v); } }
    return h("div", { className: cx("cl-prompt", p.className) },
      h("textarea", { className: "cl-prompt-input", rows: p.rows || 2, value: v, placeholder: p.placeholder || "Ask anything…", "aria-label": p.label || "Prompt",
        onChange: function (e) { setV(e.target.value); },
        onKeyDown: function (e) { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); send(); } } }),
      h("div", { className: "cl-prompt-bar" },
        p.tools || null,
        h("span", { className: "cl-prompt-meta" }, p.meta || ""),
        h(Button, { size: "sm", icon: "arrow_upward", onClick: send, disabled: p.busy || !v.trim(), "aria-label": "Send" }, p.busy ? "Running…" : "Send")));
  }

  function Tabs(p) {
    var items = p.items || [];
    var st = React.useState(p.defaultValue || (items[0] && items[0].value)), cur = p.value !== undefined ? p.value : st[0];
    function pick(v) { if (p.value === undefined) st[1](v); if (p.onChange) p.onChange(v); }
    return h("div", { className: cx("cl-tabs", p.className), role: "tablist", "aria-label": p.label },
      items.map(function (it) {
        return h("button", { key: it.value, type: "button", role: "tab", className: "cl-tab", "aria-selected": cur === it.value ? "true" : "false", onClick: function () { pick(it.value); } },
          it.icon ? h(Icon, { name: it.icon, size: 18 }) : null, it.label, it.count != null ? h("span", { className: "cl-tab-count" }, it.count) : null);
      }));
  }

  function Switch(p) {
    var st = React.useState(!!p.defaultChecked), on = p.checked !== undefined ? p.checked : st[0];
    function flip() { if (p.disabled) return; if (p.checked === undefined) st[1](!on); if (p.onChange) p.onChange(!on); }
    var btn = h("button", { type: "button", role: "switch", "aria-checked": on ? "true" : "false", className: "cl-switch", disabled: p.disabled, onClick: flip, "aria-label": p.label ? undefined : p["aria-label"] });
    return p.label ? h("label", { className: cx("cl-switch-row", p.className) }, btn, h("span", null, p.label)) : btn;
  }

  function Card(p) {
    var rest = omit(p, ["eyebrow", "title", "actions", "footer", "flat", "className", "children"]);
    return h("section", Object.assign({}, rest, { className: cx("cl-card", p.flat && "cl-card-flat", p.className) }),
      (p.title || p.eyebrow || p.actions) ? h("div", { className: "cl-card-head" },
        h("div", null, p.eyebrow ? h("p", { className: "cl-card-eyebrow" }, p.eyebrow) : null, p.title ? h("h3", { className: "cl-card-title" }, p.title) : null),
        p.actions || null) : null,
      typeof p.children === "string" ? h("p", { className: "cl-card-body" }, p.children) : p.children,
      p.footer ? h("div", { className: "cl-card-foot" }, p.footer) : null);
  }

  function Metric(p) {
    var dir = p.trend || "neutral";
    var icon = dir === "up" ? "trending_up" : dir === "down" ? "trending_down" : "trending_flat";
    var good = p.good === undefined ? dir === "up" : p.good;
    return h("div", { className: cx("cl-metric", p.className) },
      h("span", { className: "cl-metric-label" }, p.label),
      h("span", { className: "cl-metric-value" }, p.value, p.unit ? h("span", { className: "cl-metric-unit" }, p.unit) : null),
      p.delta ? h("span", { className: cx("cl-metric-delta", dir !== "neutral" && (good ? "cl-metric-delta-good" : "cl-metric-delta-bad")) }, h(Icon, { name: icon }), p.delta) : null);
  }

  function Table(p) {
    var cols = p.columns || [], rows = p.rows || [];
    return h("div", { className: cx("cl-table-wrap", p.className) },
      h("table", { className: "cl-table" },
        p.caption ? h("caption", { style: { position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" } }, p.caption) : null,
        h("thead", null, h("tr", null, cols.map(function (c) { return h("th", { key: c.key, scope: "col", className: c.align === "right" ? "cl-num" : undefined }, c.label); }))),
        h("tbody", null, rows.map(function (r, i) {
          return h("tr", { key: r.id || i }, cols.map(function (c) {
            var v = c.render ? c.render(r) : r[c.key];
            return h("td", { key: c.key, className: cx(c.align === "right" && "cl-num", c.mono && "cl-mono") }, v);
          }));
        }))));
  }

  var BADGE_ICON = { success: "check", warning: "warning", danger: "error" };
  function Badge(p) {
    var tone = p.tone || "neutral";
    var ic = p.icon === false ? null : (p.icon || BADGE_ICON[tone]);
    return h("span", { className: cx("cl-badge", "cl-badge-" + tone, p.className) }, ic ? h(Icon, { name: ic }) : null, p.children);
  }

  var BANNER_ICON = { info: "info", success: "check_circle", warning: "warning", danger: "error" };
  function Banner(p) {
    var tone = p.tone || "info";
    return h("div", { className: cx("cl-banner", "cl-banner-" + tone, p.className), role: tone === "danger" ? "alert" : "status" },
      h(Icon, { name: p.icon || BANNER_ICON[tone] }),
      h("div", { className: "cl-banner-body" }, p.title ? h("p", { className: "cl-banner-title" }, p.title) : null, p.children ? h("p", { className: "cl-banner-text" }, p.children) : null),
      p.action || null);
  }

  function TopBar(p) {
    return h("header", { className: cx("cl-topbar", p.className) },
      h("span", { className: "cl-topbar-mark", "aria-hidden": "true" }, h(Icon, { name: p.markIcon || "bolt" })),
      h("span", { className: "cl-topbar-name" }, p.product),
      p.context ? h("span", { className: "cl-topbar-context" }, p.context) : null,
      h("span", { className: "cl-topbar-spacer" }),
      p.actions ? h("div", { className: "cl-topbar-actions" }, p.actions) : null);
  }

  window.Clearline = Object.assign(window.Clearline || {}, { TopBar: TopBar, Button: Button, TextField: TextField, PromptBox: PromptBox, Tabs: Tabs, Switch: Switch, Card: Card, Metric: Metric, Table: Table, Badge: Badge, Banner: Banner, Icon: Icon });
})();
