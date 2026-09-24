/* Sales & expenses: the company's own records, monthly figures, legal limits and bank statement import.
   Uses the page's helpers ($, el, t, tp, api, formatAmount, monthYear, shortDate, currentCompany, currentProfile).
   Every tax figure shown here comes from the server's rules engine; this file only displays it. */
(() => {
  const gel = (value) => `${formatAmount(value)} ${t("card.currency")}`;
  const monthKey = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  const monthStartIso = (key) => `${key}-01`;
  const monthEndIso = (key) => {
    const [y, m] = key.split("-").map(Number);
    return `${key}-${String(new Date(y, m, 0).getDate()).padStart(2, "0")}`;
  };
  const shiftMonth = (key, by) => {
    const [y, m] = key.split("-").map(Number);
    return monthKey(new Date(y, m - 1 + by, 1));
  };

  let open = false;
  let month = monthKey(new Date());
  let summary = null;
  let records = [];
  let adding = false;
  let loadToken = 0;

  /* ---------- view switching ---------- */
  function show() {
    if (!currentCompany()) return;
    open = true;
    document.body.classList.add("books-open");
    $("books").hidden = false;
    $("app").classList.remove("drawer-open");
    $("title").textContent = t("books.title") + " · " + currentCompany().name;
    load();
  }

  function hide() {
    if (!open) return;
    open = false;
    document.body.classList.remove("books-open");
    $("books").hidden = true;
    const company = currentCompany();
    if (company) $("title").textContent = company.name;
  }

  /* ---------- data ---------- */
  async function load() {
    const company = currentCompany();
    if (!company) return;
    const token = ++loadToken;
    try {
      const [s, list] = await Promise.all([
        api(`/companies/${company.id}/books?month=${month}`),
        api(`/companies/${company.id}/transactions?start=${monthStartIso(month)}&end=${monthEndIso(month)}`),
      ]);
      if (token !== loadToken) return;
      summary = s;
      records = list.slice().reverse();
    } catch (err) {
      if (err instanceof AuthError) return;
      summary = null;
      records = [];
    }
    render();
    renderAlert();
  }

  // The sidebar alert always looks at the current month, whichever month the view shows.
  async function loadAlert() {
    const company = currentCompany();
    const box = $("booksAlert");
    if (!company) { box.hidden = true; return; }
    try {
      const s = await api(`/companies/${company.id}/books`);
      renderAlert(s);
    } catch { box.hidden = true; }
  }

  let alertSummary = null;
  function alerts(s) {
    if (!s) return [];
    const found = [];
    const vat = s.turnover_12m;
    if (vat && vat.alert !== "none") {
      found.push({ level: vat.alert, text: t(`books.alert.vat.${vat.alert}`, { amount: gel(vat.amount), limit: gel(vat.limit) }) });
    }
    const year = s.year_income;
    if (year && year.alert !== "none") {
      found.push({ level: year.alert, text: t(`books.alert.sb.${year.alert}`, { amount: gel(year.amount), limit: gel(year.limit) }) });
    }
    return found;
  }

  function renderAlert(s) {
    if (s !== undefined) alertSummary = s;
    const box = $("booksAlert");
    const list = alerts(alertSummary);
    box.hidden = !list.length;
    box.replaceChildren(...list.map((a) => el("div", { class: `books-alert ${a.level}`, role: "status" },
      el("span", { class: "alert-icon", "aria-hidden": "true", text: a.level === "exceeded" ? "!" : "i" }),
      el("span", { text: a.text }))));
  }

  /* ---------- rendering ---------- */
  function card(label, value, extra = {}) {
    return el("div", { class: "books-card" + (extra.tone ? " " + extra.tone : "") },
      el("span", { class: "books-card-label", text: label }),
      el("span", { class: "books-card-value", text: value }),
      extra.hint ? el("span", { class: "books-card-hint", text: extra.hint }) : null);
  }

  function limitBar(label, status, hint) {
    const limit = Number(status.limit);
    const share = limit ? Math.min(Number(status.amount) / limit, 1) : 0;
    return el("div", { class: `books-limit ${status.alert}` },
      el("div", { class: "books-limit-head" },
        el("span", { text: label }),
        el("strong", { text: `${gel(status.amount)} / ${gel(status.limit)}` })),
      el("div", { class: "books-bar", role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100",
                  "aria-valuenow": String(Math.round(share * 100)) },
        el("span", { style: `width:${(share * 100).toFixed(1)}%` })),
      el("p", { class: "books-limit-hint", text: hint }));
  }

  function copyButton(value) {
    const button = el("button", { class: "btn small copy", type: "button", text: t("books.copy") });
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(String(value));
        button.textContent = t("books.copied");
        setTimeout(() => { button.textContent = t("books.copy"); }, 1500);
      } catch { /* clipboard blocked; the figure is on screen anyway */ }
    });
    return button;
  }

  function returnLine(label, value) {
    return el("div", { class: "return-line" }, el("span", { text: label }),
      el("strong", { text: gel(value) }), copyButton(value));
  }

  function returnsPanel(s) {
    const blocks = [];
    const breakdown = (r) => Object.fromEntries((r.breakdown || []).map((b) => [b.name, b.amount]));
    if (s.vat_payable && s.vat_payable.status === "applies") {
      const b = breakdown(s.vat_payable);
      blocks.push(el("div", { class: "return-block" }, el("h4", { text: t("books.returnVat") }),
        returnLine(t("books.outputVat"), s.totals.output_vat),
        returnLine(t("books.inputVat"), s.totals.input_vat),
        Number(b.excess_credit) > 0 ? returnLine(t("books.vatRefund"), b.excess_credit) : returnLine(t("books.vatPayable"), b.payable)));
    }
    if (s.small_business_tax && s.small_business_tax.status === "applies") {
      blocks.push(el("div", { class: "return-block" }, el("h4", { text: t("books.returnSb") }),
        returnLine(t("books.income"), s.totals.income),
        returnLine(t("books.sbTax"), s.small_business_tax.amount)));
    }
    if (!blocks.length) return null;
    return el("section", { class: "books-panel" },
      el("h3", { text: t("books.returns") }),
      el("p", { class: "books-muted", text: t("books.returnsHint", { month: monthYear(monthStartIso(month)) }) }),
      el("div", { class: "return-grid" }, blocks),
      el("p", { class: "books-muted small", text: t("books.unverified") }));
  }

  function recordRow(r) {
    const who = [r.counterparty, r.description].filter(Boolean).join(" · ");
    const remove = el("button", { class: "icon-btn small-icon", type: "button", title: t("books.delete"), "aria-label": t("books.delete") });
    remove.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>';
    remove.addEventListener("click", async () => {
      if (!confirm(t("books.confirmDelete"))) return;
      try {
        await api(`/companies/${currentCompany().id}/transactions/${r.id}`, { method: "DELETE" });
        load();
      } catch (err) { if (!(err instanceof AuthError)) alert(err.message); }
    });
    return el("tr", { class: r.direction },
      el("td", { class: "nowrap", text: shortDate(r.occurred_on) }),
      el("td", { class: "who", text: who || "—", title: who }),
      el("td", {}, el("span", { class: `tag ${r.direction}`, text: t(`books.type.${r.direction}`) })),
      el("td", { class: "num", text: (r.direction === "expense" ? "−" : "") + gel(r.amount) }),
      el("td", { class: "num muted", text: r.vat_amount ? gel(r.vat_amount) : "—" }),
      el("td", { class: "actions" }, remove));
  }

  function addForm() {
    const vatRegistered = !!(currentProfile && currentProfile.vat_registered);
    const form = el("form", { class: "books-form", novalidate: "true" },
      el("label", {}, el("span", { text: t("books.form.date") }),
        el("input", { class: "field", type: "date", name: "occurred_on", required: "true",
                      value: month === monthKey(new Date()) ? new Date().toISOString().slice(0, 10) : monthStartIso(month) })),
      el("label", {}, el("span", { text: t("books.form.type") }),
        el("select", { class: "field", name: "direction" },
          el("option", { value: "income", text: t("books.type.income") }),
          el("option", { value: "expense", text: t("books.type.expense") }))),
      el("label", {}, el("span", { text: t("books.form.amount") }),
        el("input", { class: "field", name: "amount", inputmode: "decimal", required: "true", placeholder: "0.00" })),
      el("label", { class: "wide" }, el("span", { text: t("books.form.counterparty") }),
        el("input", { class: "field", name: "counterparty", maxlength: "255" })),
      el("label", { class: "wide" }, el("span", { text: t("books.form.description") }),
        el("input", { class: "field", name: "description", maxlength: "1000" })),
      vatRegistered ? el("label", { class: "check wide" }, el("input", { type: "checkbox", name: "vat_included", checked: "true" }),
        el("span", { text: t("books.form.vatAuto") })) : null,
      el("p", { class: "form-error wide", role: "alert" }),
      el("div", { class: "dialog-actions wide" },
        el("button", { class: "btn", type: "button", text: t("common.cancel"), onclick: () => { adding = false; render(); } }),
        el("button", { class: "btn primary", type: "submit", text: t("books.form.save") })));
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = form.elements;
      const amount = f.amount.value.replace(/\s/g, "").replace(",", ".");
      if (!f.occurred_on.value || !/^\d+(\.\d{1,2})?$/.test(amount) || Number(amount) <= 0) {
        form.querySelector(".form-error").textContent = t("books.form.required");
        return;
      }
      try {
        await api(`/companies/${currentCompany().id}/transactions`, { method: "POST", body: {
          occurred_on: f.occurred_on.value, direction: f.direction.value, amount,
          vat_included: !!(f.vat_included && f.vat_included.checked),
          category: f.direction.value === "income" ? "sales" : "purchase",
          counterparty: f.counterparty.value.trim() || null, description: f.description.value.trim() || null,
        } });
        adding = false;
        month = f.occurred_on.value.slice(0, 7);
        load();
      } catch (err) {
        if (!(err instanceof AuthError)) form.querySelector(".form-error").textContent = err.message;
      }
    });
    setTimeout(() => form.elements.amount.focus(), 0);
    return form;
  }

  function render() {
    if (!open) return;
    const s = summary;
    const head = el("div", { class: "books-head" },
      el("div", { class: "month-nav" },
        el("button", { class: "icon-btn", type: "button", title: t("books.prevMonth"), "aria-label": t("books.prevMonth"),
                       text: "‹", onclick: () => { month = shiftMonth(month, -1); load(); } }),
        el("strong", { class: "month-label", text: monthYear(monthStartIso(month)) }),
        el("button", { class: "icon-btn", type: "button", title: t("books.nextMonth"), "aria-label": t("books.nextMonth"),
                       text: "›", onclick: () => { month = shiftMonth(month, 1); load(); } })),
      el("div", { class: "books-actions" },
        el("button", { class: "btn", type: "button", text: t("books.import"), onclick: openImport }),
        el("button", { class: "btn primary", type: "button", text: t("books.add"),
                       onclick: () => { adding = true; render(); } })));

    const parts = [head];
    if (s) {
      const list = alerts(s);
      if (list.length) parts.push(el("div", { class: "books-alerts" }, list.map((a) =>
        el("div", { class: `books-alert ${a.level}`, role: "status" },
          el("span", { class: "alert-icon", "aria-hidden": "true", text: a.level === "exceeded" ? "!" : "i" }),
          el("span", { text: a.text })))));

      const cards = [
        card(t("books.income"), gel(s.totals.income), { hint: tp("books.count", s.totals.count) }),
        card(t("books.expense"), gel(s.totals.expense)),
      ];
      if (s.vat_payable) {
        const b = Object.fromEntries((s.vat_payable.breakdown || []).map((x) => [x.name, x.amount]));
        cards.push(card(t("books.outputVat"), gel(s.totals.output_vat)), card(t("books.inputVat"), gel(s.totals.input_vat)));
        cards.push(Number(b.excess_credit) > 0
          ? card(t("books.vatRefund"), gel(b.excess_credit), { tone: "ok" })
          : card(t("books.vatPayable"), gel(b.payable || "0.00"), { tone: "accent" }));
      }
      if (s.small_business_tax && s.small_business_tax.status === "applies") {
        cards.push(card(t("books.sbTax"), gel(s.small_business_tax.amount), { tone: "accent" }));
      }
      parts.push(el("div", { class: "books-cards" }, cards));

      const limits = [];
      if (s.vat_registration) {
        limits.push(limitBar(t("books.turnover"), s.turnover_12m, t("books.turnoverHint", {
          start: monthYear(s.turnover_12m.start), end: monthYear(s.turnover_12m.end), limit: gel(s.turnover_12m.limit) })));
      }
      if (s.year_income) {
        limits.push(limitBar(t("books.yearIncome"), s.year_income, t("books.yearHint", { limit: gel(s.year_income.limit) })));
      }
      if (limits.length) parts.push(el("section", { class: "books-panel" }, limits));
      const returns = returnsPanel(s);
      if (returns) parts.push(returns);
    }

    if (adding) parts.push(el("section", { class: "books-panel" }, el("h3", { text: t("books.addTitle") }), addForm()));

    const table = records.length
      ? el("div", { class: "books-table-wrap" }, el("table", { class: "books-table" },
          el("thead", {}, el("tr", {},
            ["date", "who", "type", "amount", "vat", ""].map((c) =>
              el("th", { class: c === "amount" || c === "vat" ? "num" : "", text: c ? t(`books.col.${c}`) : "" })))),
          el("tbody", {}, records.map(recordRow))))
      : el("p", { class: "books-empty", text: t("books.empty") });
    parts.push(el("section", { class: "books-panel" }, el("h3", { text: t("books.records") }), table));

    $("booksInner").replaceChildren(...parts);
  }

  /* ---------- import ---------- */
  let importState = null;  // { filename, content, preview, mapping }

  function importDialog() {
    let dialog = $("importDialog");
    if (!dialog) {
      dialog = el("dialog", { id: "importDialog", class: "import-dialog" });
      document.body.append(dialog);
    }
    return dialog;
  }

  function openImport() {
    importState = null;
    renderImport();
    importDialog().showModal();
  }

  function readFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });
  }

  async function preview(mapping) {
    importState.error = "";
    importState.loading = true;
    renderImport();
    try {
      importState.preview = await api(`/companies/${currentCompany().id}/books/import/preview`, { method: "POST",
        body: { filename: importState.filename, content: importState.content, mapping } });
      importState.mapping = importState.preview.mapping;
    } catch (err) {
      if (err instanceof AuthError) { importDialog().close(); return; }
      importState.preview = null;
      importState.error = err.message;
    }
    importState.loading = false;
    renderImport();
  }

  function renderImport() {
    const dialog = importDialog();
    const vatRegistered = !!(currentProfile && currentProfile.vat_registered);
    const file = el("input", { type: "file", accept: ".csv,.txt,.xlsx", class: "file-input", id: "importFile" });
    file.addEventListener("change", async () => {
      const chosen = file.files[0];
      if (!chosen) return;
      importState = { filename: chosen.name, content: await readFile(chosen), preview: null, mapping: null, done: null };
      preview(null);
    });
    const parts = [
      el("h3", { text: t("import.title") }),
      el("p", { class: "books-muted", text: t("import.desc") }),
      el("label", { class: "file-pick" }, file, el("span", { class: "btn", text: t("import.choose") }),
        el("span", { class: "file-name", text: importState ? importState.filename : t("import.noFile") })),
    ];
    const st = importState;
    if (st && st.loading) parts.push(el("p", { class: "books-muted", text: t("import.reading") }));
    if (st && st.error) parts.push(el("p", { class: "form-error", role: "alert", text: st.error }));

    if (st && st.done) {
      parts.push(el("p", { class: "import-done", role: "status", text: t("import.done", st.done) }));
      parts.push(el("div", { class: "dialog-actions" },
        el("button", { class: "btn primary", type: "button", text: t("import.close"), onclick: () => dialog.close() })));
      dialog.replaceChildren(el("div", { class: "form-grid" }, parts));
      return;
    }

    if (st && st.preview) {
      const p = st.preview;
      const selects = ["date", "amount", "income", "expense", "counterparty", "description"].map((column) => {
        const select = el("select", { class: "field", "data-column": column },
          el("option", { value: "", text: t("import.none") }),
          p.header.map((name, i) => el("option", { value: String(i), text: name || `#${i + 1}` })));
        select.value = p.mapping[column] === null || p.mapping[column] === undefined ? "" : String(p.mapping[column]);
        select.addEventListener("change", () => {
          const mapping = { ...st.mapping, [column]: select.value === "" ? null : Number(select.value) };
          preview(mapping);
        });
        return el("label", {}, el("span", { text: t(`import.col.${column}`) }), select);
      });
      parts.push(el("div", { class: "import-columns" }, selects));
      parts.push(el("p", { class: "books-muted", text: t("import.found", { total: p.total, income: p.income, expense: p.expense }) +
        (p.duplicates ? " " + t("import.duplicates", { n: p.duplicates }) : "") +
        (p.skipped.length ? " " + t("import.skipped", { n: p.skipped.length }) : "") }));
      if (p.rows.length) {
        parts.push(el("div", { class: "books-table-wrap preview" }, el("table", { class: "books-table" },
          el("thead", {}, el("tr", {}, ["date", "who", "type", "amount"].map((c) =>
            el("th", { class: c === "amount" ? "num" : "", text: t(`books.col.${c}`) })))),
          el("tbody", {}, p.rows.map((r) => el("tr", {},
            el("td", { class: "nowrap", text: shortDate(r.occurred_on) }),
            el("td", { class: "who", text: [r.counterparty, r.description].filter(Boolean).join(" · ") || "—" }),
            el("td", {}, el("span", { class: `tag ${r.direction}`, text: t(`books.type.${r.direction}`) })),
            el("td", { class: "num", text: gel(r.amount) })))))));
      }
      const salesVat = el("input", { type: "checkbox", id: "importSalesVat", checked: vatRegistered ? "true" : null });
      const purchasesVat = el("input", { type: "checkbox", id: "importPurchasesVat" });
      if (vatRegistered) {
        parts.push(el("label", { class: "check" }, salesVat, el("span", { text: t("import.salesVat") })));
        parts.push(el("label", { class: "check" }, purchasesVat, el("span", { text: t("import.purchasesVat") })));
      }
      const newRows = p.total - p.duplicates;
      const go = el("button", { class: "btn primary", type: "button", text: t("import.confirm", { n: newRows }),
                                disabled: newRows <= 0 ? "true" : null });
      go.addEventListener("click", async () => {
        go.disabled = true;
        try {
          const result = await api(`/companies/${currentCompany().id}/books/import`, { method: "POST", body: {
            filename: st.filename, content: st.content, mapping: st.mapping,
            sales_include_vat: vatRegistered && salesVat.checked, purchases_include_vat: vatRegistered && purchasesVat.checked,
          } });
          st.done = result;
          renderImport();
          load();
          loadAlert();
        } catch (err) {
          go.disabled = false;
          if (!(err instanceof AuthError)) { st.error = err.message; renderImport(); }
        }
      });
      parts.push(el("div", { class: "dialog-actions" },
        el("button", { class: "btn", type: "button", text: t("common.cancel"), onclick: () => dialog.close() }), go));
    } else {
      parts.push(el("div", { class: "dialog-actions" },
        el("button", { class: "btn", type: "button", text: t("common.cancel"), onclick: () => dialog.close() })));
    }
    dialog.replaceChildren(el("div", { class: "form-grid" }, parts));
  }

  /* ---------- hooks for the page ---------- */
  $("booksBtn").addEventListener("click", () => (open ? hide() : show()));
  window.Books = {
    show, hide,
    get open() { return open; },
    onCompanyChange() { summary = null; records = []; adding = false; if (open) show(); loadAlert(); },
    onLanguageChange() {
      if (open) { $("title").textContent = t("books.title") + " · " + (currentCompany() || {}).name; render(); }
      renderAlert();
      if ($("importDialog") && $("importDialog").open) renderImport();
    },
  };
  if (typeof user !== "undefined" && user && currentCompany()) loadAlert();
})();
