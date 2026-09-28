/* Overview (home) and the tax calendar. Figures come from the server: deadlines with their amounts, and the books
   summary (rule results on recorded sales). This file only arranges them.
   Uses the page's helpers ($, el, t, tp, loc, api, formatAmount, monthYear, shortDate, fullDate, currentCompany,
   currentProfile, deadlineItems, user, go, ask, openCompanyDialog, AuthError). */
(() => {
  const gel = (value) => `${formatAmount(value)} ${t("card.currency")}`;
  const iso = (d) => d.toISOString().slice(0, 10);
  const monthKey = (isoDate) => isoDate.slice(0, 7);
  const prevMonthKey = (key) => {
    const [y, m] = key.split("-").map(Number);
    return m === 1 ? `${y - 1}-12` : `${y}-${String(m - 1).padStart(2, "0")}`;
  };
  const periodLabel = (d) => d.period_start.slice(0, 7) === d.period_end.slice(0, 7)
    ? monthYear(d.period_start) : d.period_start.slice(0, 4);
  function whenText(d) {
    if (d.state === "done") return d.paid_amount != null ? t("deadlines.paid", { amount: gel(d.paid_amount) }) : t("cal.done");
    const left = d.days_left < 0 ? tp("deadlines.overdue", -d.days_left)
      : d.days_left === 0 ? t("deadlines.today") : d.days_left === 1 ? t("deadlines.tomorrow") : tp("deadlines.inDays", d.days_left);
    return `${t("deadlines.by", { date: shortDate(d.due_date) })} · ${left}`;
  }
  const icon = (d, size = 18) => {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    for (const [k, v] of Object.entries({ width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
      "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" })) svg.setAttribute(k, v);
    const path = document.createElementNS(ns, "path");
    path.setAttribute("d", d);
    svg.append(path);
    return svg;
  };
  const CHECK = "M20 6L9 17l-5-5";

  function dateBadge(d) {
    const [, m, day] = d.due_date.split("-").map(Number);
    return el("div", { class: `date-badge ${d.tax_type}` + (d.state === "overdue" ? " overdue" : "") },
      el("b", { text: String(day) }), el("span", { text: lookup("date.monthsShort")[m - 1] }));
  }

  const payButton = (d, primary = false) => d.payment && d.state !== "done"
    ? el("button", { class: "btn" + (primary ? " primary" : " small"), type: "button", text: t("deadlines.pay"),
        onclick: () => window.Pay?.open(d) })
    : null;

  /* ---------- overview ---------- */
  let ovOpen = false;
  let summary = null;     // books summary for this month
  let previous = null;    // and the month before
  let setup = null;       // { rs, banks, records }
  let token = 0;

  function greeting() {
    const h = new Date().getHours();
    return t(h < 12 ? "ov.morning" : h < 18 ? "ov.afternoon" : "ov.evening");
  }

  async function load() {
    const company = currentCompany();
    const mine = ++token;
    if (!company) { summary = previous = null; setup = { rs: null, banks: [], records: false }; render(); return; }
    const month = monthKey($("asOf").value || iso(new Date()));
    try {
      const [s, p, rs, banks, records] = await Promise.all([
        api(`/companies/${company.id}/books?month=${month}`),
        api(`/companies/${company.id}/books?month=${prevMonthKey(month)}`),
        api(`/companies/${company.id}/rs`),
        api(`/companies/${company.id}/banks`),
        api(`/companies/${company.id}/transactions`),
      ]);
      if (mine !== token) return;
      summary = s; previous = p;
      setup = { rs, banks, records: records.length > 0 };
      $("companiesDot").hidden = rs.connected;
    } catch (err) {
      if (err instanceof AuthError || mine !== token) return;
      summary = previous = null;
    }
    render();
  }

  function heroCard(open) {
    // Soonest first; on the same day, one whose amount is known from the books.
    const next = open.filter((d) => d.payment)
      .sort((x, y) => x.days_left - y.days_left || (x.amount_due == null) - (y.amount_due == null))[0];
    const card = el("section", { class: "panel hero" });
    if (!next) {
      card.append(el("div", { class: "panel-head" }, el("h2", { class: "muted", text: t("ov.nextPayment") })),
        el("div", { class: "hero-amount none", text: t("payments.nothing") }));
      return card;
    }
    const chip = next.state === "overdue" ? el("span", { class: "state bad", text: tp("deadlines.overdue", -next.days_left) })
      : next.state === "due_soon" ? el("span", { class: "state todo", text: whenText(next) }) : null;
    const fromBooks = next.amount_due != null;
    card.append(
      el("div", { class: "panel-head" }, el("h2", { class: "muted", text: t("ov.nextPayment") }), chip),
      el("div", { class: "hero-body" },
        el("div", {},
          el("div", { class: "hero-amount" + (fromBooks ? "" : " none"), text: fromBooks ? gel(next.amount_due) : t("payments.noAmount") }),
          el("div", { class: "hero-title", text: `${loc(next.title)} · ${periodLabel(next)}` }),
          el("div", { class: "hero-sub", text: whenText(next) }),
          penaltyText(next) ? el("div", { class: "hero-penalty", text: penaltyText(next) }) : null),
        el("div", { class: "hero-actions" },
          fromBooks ? el("button", { class: "btn", type: "button", text: t("ov.howCalculated"), onclick: () => go("books") }) : null,
          payButton(next, true))));
    return card;
  }

  const UP = "M7 17L17 7M9 7h8v8", DOWN = "M7 7l10 10M17 9v8H9", PERCENT = "M19 5L5 19M6.5 9a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM17.5 20a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z";

  function stat(label, value, hint, hintClass = "", tone = "", path = PERCENT) {
    return el("div", { class: "stat " + tone },
      el("div", { class: "stat-top" }, el("span", { class: "stat-ico" }, icon(path, 16)), el("span", { class: "stat-label", text: label })),
      el("span", { class: "stat-value", text: value }),
      hint ? el("span", { class: "stat-hint " + hintClass, text: hint }) : null);
  }

  function statsRow() {
    if (!summary) return null;
    const month = monthYear(summary.month);
    const income = Number(summary.totals.income), before = previous ? Number(previous.totals.income) : 0;
    const pct = before > 0 ? Math.round(((income - before) / before) * 100) : null;
    const change = pct === null || pct === 0 ? null : t("ov.change", { pct: `${pct > 0 ? "+" : ""}${pct}%` });
    const third = summary.vat_payable && summary.vat_payable.status === "applies"
      ? stat(t("ov.vatDue", { month }), gel(summary.vat_payable.amount), null, "", "wine")
      : summary.small_business_tax && summary.small_business_tax.status === "applies"
        ? stat(t("ov.sbDue", { month }), gel(summary.small_business_tax.amount), null, "", "wine")
        : stat(t("books.turnover"), gel(summary.turnover_12m.amount),
            summary.turnover_12m.limit ? `/ ${gel(summary.turnover_12m.limit)}` : null, "", "blue");
    return el("div", { class: "stats" },
      stat(t("ov.sales", { month }), gel(summary.totals.income), change, pct > 0 ? "up" : "", "green", UP),
      stat(t("ov.expenses", { month }), gel(summary.totals.expense), tp("books.count", summary.totals.count), "", "amber", DOWN),
      third);
  }

  function upcomingCard(open) {
    const rows = open.slice(0, 5).map((d) => el("div", { class: `dl-row ${d.state}` },
      dateBadge(d),
      el("div", { class: "dl-text" }, el("span", { class: "dl-title", text: `${loc(d.title)} · ${periodLabel(d)}` }),
        el("span", { class: "dl-when", text: whenText(d) }),
        penaltyText(d) ? el("span", { class: "dl-penalty", text: penaltyText(d) }) : null),
      d.amount_due != null ? el("span", { class: "dl-amount", text: gel(d.amount_due) })
        : el("span", { class: "dl-amount none", text: d.payment ? t("payments.noAmount") : "" }),
      payButton(d) || el("span")));
    return el("section", { class: "panel" },
      el("div", { class: "panel-head" }, el("h2", { text: t("ov.upcoming") }),
        el("button", { class: "link-btn", type: "button", text: t("ov.toCalendar"), onclick: () => go("calendar") })),
      rows.length ? el("div", {}, rows) : el("p", { class: "muted", text: t("deadlines.none") }));
  }

  function setupCard() {
    const company = currentCompany();
    const s = setup || { rs: null, banks: [], records: false };
    const steps = [
      { done: !!company, title: t("ov.setup.company"), hint: null, action: openCompanyDialog },
      { done: !!(s.rs && s.rs.connected), title: t("ov.setup.rs"), hint: t("ov.setup.rsHint"), action: () => go("companies") },
      { done: s.banks.length > 0, title: t("ov.setup.bank"), hint: t("ov.setup.bankHint"), action: () => go("banks") },
      { done: s.records, title: t("ov.setup.statement"), hint: t("ov.setup.statementHint"),
        action: () => (company ? window.Books?.openImport() : openCompanyDialog()) },
    ];
    const done = steps.filter((x) => x.done).length;
    if (done === steps.length) return null;
    const firstOpen = steps.find((x) => !x.done);
    return el("section", { class: "panel" },
      el("div", { class: "panel-head" }, el("h2", { text: t("ov.setup") }), el("span", { class: "muted", text: `${done} / ${steps.length}` })),
      el("div", { class: "progress" }, el("span", { style: `width:${(100 * done / steps.length).toFixed(0)}%` })),
      el("div", { class: "steps" }, steps.map((x) => {
        const inner = [
          el("span", { class: "step-mark" }, x.done ? icon(CHECK, 13) : null),
          el("span", { class: "step-text" }, el("b", { text: x.title }), !x.done && x.hint ? el("span", { text: x.hint }) : null),
        ];
        return x.done ? el("div", { class: "step done" }, inner)
          : el("button", { class: "step" + (x === firstOpen ? " next" : ""), type: "button", onclick: x.action }, inner,
              el("span", { "aria-hidden": "true", text: "→" }));
      })));
  }

  function quickCard() {
    const quick = (d, text, action, colour) => el("button", { class: "quick", type: "button", onclick: action },
      el("span", { class: "quick-ico", style: `--c:var(--c-${colour})` }, icon(d)), el("span", { text }));
    return el("section", { class: "panel" }, el("h2", { text: t("ov.quick") }),
      quick("M12 5v14M5 12h14", t("ov.addRecord"), () => { window.Books?.startAdd(); go("books"); }, "teal"),
      quick("M12 15V3M7 8l5-5 5 5M4 17v3h16v-3", t("ov.setup.statement"), () => window.Books?.openImport(), "green"),
      quick("M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z", t("ov.ask"), () => { go("assistant"); $("message").focus(); }, "violet"));
  }

  function render() {
    if (!ovOpen) return;
    const company = currentCompany();
    const open = deadlineItems.filter((d) => d.state !== "done").sort((a, b) => a.days_left - b.days_left);
    const overdue = open.filter((d) => d.state === "overdue").length;
    const head = el("div", { class: "page-head" }, el("div", {},
      el("h1", { text: greeting() }),
      el("p", { text: company ? `${fullDate(new Date())} · ${overdue ? tp("ov.overdue", overdue) : t("ov.allClear")}` : fullDate(new Date()) })));
    if (!company) {
      const first = user ? user.full_name.split(" ")[0] : "";
      $("overviewInner").replaceChildren(head, el("div", { class: "ov-grid" },
        el("section", { class: "panel hero welcome" },
          el("h2", { text: first ? t("welcome.title", { name: first }) : t("welcome.titleNoName") }),
          el("p", { class: "muted", text: t("welcome.desc") }),
          el("div", { class: "hero-actions" }, el("button", { class: "btn primary", type: "button", text: t("welcome.add"), onclick: openCompanyDialog }))),
        el("div", { class: "ov-side" }, setupCard())));
      return;
    }
    const alertBox = $("booksAlert");
    $("overviewInner").replaceChildren(head, el("div", { class: "ov-grid" },
      el("div", { class: "ov-main" }, alertBox, heroCard(open), statsRow(), upcomingCard(open)),
      el("div", { class: "ov-side" }, setupCard(), quickCard())));
  }

  window.Overview = {
    show() { ovOpen = true; $("overview").hidden = false; render(); load(); window.Books?.loadAlert(); },
    hide() { ovOpen = false; },
    render, reload() { if (ovOpen) load(); else setup = null; },
    onCompanyChange() { summary = previous = setup = null; if (ovOpen) { render(); load(); } },
    onLanguageChange() { render(); },
  };

  /* ---------- tax calendar ---------- */
  let calOpen = false;
  let calItems = null;
  let months = 6;
  try { months = Number(localStorage.getItem("calMonths")) || 6; } catch { /* default */ }
  let calToken = 0;

  async function loadCalendar() {
    const company = currentCompany();
    if (!company) return;
    const mine = ++calToken;
    try {
      const items = await api(`/companies/${company.id}/deadlines?months=${months}&as_of=${$("asOf").value}`);
      if (mine === calToken) calItems = items;
    } catch (err) {
      if (err instanceof AuthError) return;
      calItems = [];
    }
    renderCalendar();
  }

  async function mark(d, done) {
    try {
      await api(`/companies/${currentCompany().id}/deadlines/${d.deadline_id}/${d.period_start}?as_of=${$("asOf").value}`,
        { method: "PUT", body: { done } });
    } catch (err) {
      if (!(err instanceof AuthError)) alert(err.message);
    }
    loadDeadlines();
    loadCalendar();
  }

  function renderCalendar() {
    if (!calOpen) return;
    const range = el("select", { class: "field", style: "width:auto", "aria-label": t("nav.calendar") },
      [3, 6, 12].map((n) => el("option", { value: String(n), text: tp("cal.months", n), selected: n === months ? "true" : null })));
    range.addEventListener("change", () => {
      months = Number(range.value);
      try { localStorage.setItem("calMonths", String(months)); } catch { /* not saved */ }
      loadCalendar();
    });
    const parts = [el("div", { class: "page-head" },
      el("div", {}, el("h1", { text: t("nav.calendar") }), el("p", { text: t("cal.desc") })), range)];
    const items = calItems || [];
    if (calItems && !items.length) parts.push(el("section", { class: "panel" }, el("p", { class: "muted", text: t("deadlines.none") })));
    const byMonth = new Map();
    for (const d of [...items].sort((a, b) => a.due_date.localeCompare(b.due_date) || loc(a.title).localeCompare(loc(b.title)))) {
      const key = monthKey(d.due_date);
      byMonth.set(key, [...(byMonth.get(key) || []), d]);
    }
    for (const [key, list] of byMonth) {
      parts.push(el("section", { class: "panel cal-month" }, el("h3", { text: monthYear(`${key}-01`) }),
        list.map((d) => {
          const check = el("input", { type: "checkbox" });
          check.checked = d.state === "done";
          check.addEventListener("change", () => mark(d, check.checked));
          const amount = d.state === "done" && d.paid_amount != null ? gel(d.paid_amount)
            : d.amount_due != null ? gel(d.amount_due) : null;
          return el("div", { class: `cal-row dl-row ${d.state}` + (d.state === "done" ? " done" : "") },
            dateBadge(d),
            el("div", { class: "dl-text", title: loc(d.description) || "" },
              el("span", { class: "dl-title", text: `${loc(d.title)} · ${periodLabel(d)}` }),
              el("span", { class: "dl-when", text: whenText(d) + (d.shifted_from ? ` · ${t("deadlines.shifted", { date: shortDate(d.shifted_from) })}` : "") }),
              penaltyText(d) ? el("span", { class: "dl-penalty", text: penaltyText(d) }) : null),
            el("span", { class: "dl-amount" + (amount ? "" : " none"), text: amount || "" }),
            el("label", { class: "cal-check" }, check, el("span", { text: t("deadlines.markDone") })),
            payButton(d) || el("span"));
        })));
    }
    $("calendarInner").replaceChildren(...parts);
  }

  window.Calendar = {
    show() { calOpen = true; $("calendar").hidden = false; renderCalendar(); loadCalendar(); },
    hide() { calOpen = false; },
    render() { if (calOpen) loadCalendar(); },
    onCompanyChange() { calItems = null; if (calOpen) loadCalendar(); },
    onLanguageChange() { renderCalendar(); },
  };
})();
