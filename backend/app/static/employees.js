/* Employees: the payroll list and each month's salary declaration figures, one payroll rule result per employee.
   The app doesn't file with RS.ge (not possible yet): the owner copies the figures into the RS.ge portal.
   Also the chat's "new employee" card. Uses the page's helpers ($, el, t, api, formatAmount, shortDate, monthYear,
   currentCompany, go, loadDeadlines, initialsOf, AuthError). */
(() => {
  const gel = (value) => `${formatAmount(value)} ${t("card.currency")}`;
  const RS_PORTAL = "https://eservices.rs.ge/";
  const COLUMNS = ["gross_salary", "employee_pension", "income_tax", "net_salary", "employer_pension"];
  const HEADS = { gross_salary: "emp.col.gross", employee_pension: "emp.col.pension", income_tax: "emp.col.tax",
                  net_salary: "emp.col.net", employer_pension: "emp.col.employer" };
  const TINTS = ["rose", "teal", "violet", "blue", "amber", "green", "indigo"];
  const tint = (name) => TINTS[[...name].reduce((h, ch) => (h * 31 + ch.codePointAt(0)) % 9973, 7) % TINTS.length];

  let open = false;
  let list = null;       // employees
  let payroll = null;    // the chosen month's figures
  let month = null;      // "2026-09"
  let adding = false;
  let editing = null;    // employee id
  let token = 0;

  function thisMonth() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  }

  // "3 188,78" / "3,188.78" / "3188.78" -> "3188.78"; null if it isn't an amount.
  function parseAmount(text) {
    let v = String(text).replace(/[\s  ']/g, "");
    if (/,\d{1,2}$/.test(v)) v = v.replace(/\./g, "").replace(",", ".");
    else v = v.replace(/,/g, "");
    return /^\d+(\.\d{1,2})?$/.test(v) && Number(v) > 0 ? v : null;
  }

  async function load() {
    const company = currentCompany();
    if (!company) return;
    month = month || thisMonth();
    const mine = ++token;
    try {
      const [employees, figures] = await Promise.all([
        api(`/companies/${company.id}/employees`),
        api(`/companies/${company.id}/payroll?month=${month}-01`),
      ]);
      if (mine !== token) return;
      list = employees; payroll = figures;
    } catch (err) {
      if (err instanceof AuthError) return;
      list = []; payroll = null;
    }
    render();
  }

  function changed() {
    if (open) load();
    loadDeadlines();  // having employees puts the withholding return on the calendar
    window.Overview?.reload();
  }

  /* ---------- add / edit ---------- */
  function employeeForm(values, onSave, onCancel, saveText, withEnd) {
    const name = el("input", { class: "field", autocomplete: "off", maxlength: "255", value: values.full_name || "" });
    const pid = el("input", { class: "field", autocomplete: "off", inputmode: "numeric", maxlength: "32",
      value: values.personal_id || "" });
    const gross = el("input", { class: "field", inputmode: "decimal", value: values.gross_monthly_salary ? formatAmount(values.gross_monthly_salary) : "" });
    const start = el("input", { class: "field", type: "date", value: values.hired_on || "" });
    const end = el("input", { class: "field", type: "date", value: values.terminated_on || "" });
    const pension = el("input", { type: "checkbox", checked: values.pension_participant !== false ? "true" : null });
    const status = el("p", { class: "draft-status", role: "status" });
    const save = el("button", { class: "btn primary", type: "submit", text: saveText });
    const form = el("form", { class: "stack", novalidate: "" },
      el("div", { class: "draft-grid" },
        el("label", { class: "wide" }, el("span", { text: t("hire.name") }), name),
        el("label", {}, el("span", { text: t("hire.personalId") }), pid, el("span", { class: "field-hint", text: t("hire.personalIdHint") })),
        el("label", {}, el("span", { text: t("hire.gross") }), gross),
        el("label", {}, el("span", { text: t("hire.start") }), start),
        withEnd ? el("label", {}, el("span", { text: t("hire.end") }), end) : null,
        el("label", { class: "check wide" }, pension, el("span", { text: t("hire.pension") }))),
      status,
      el("div", { class: "actions" }, save, onCancel ? el("button", { class: "btn", type: "button", text: t("common.cancel"), onclick: onCancel }) : null));
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const amount = parseAmount(gross.value);
      if (!name.value.trim() || !pid.value.trim() || !amount || !start.value) {
        status.className = "draft-status err"; status.textContent = t("hire.required"); return;
      }
      save.disabled = true;
      try {
        await onSave({ full_name: name.value.trim(), personal_id: pid.value.replace(/\s+/g, ""), gross_monthly_salary: amount,
          hired_on: start.value, terminated_on: withEnd && end.value ? end.value : null, pension_participant: pension.checked });
      } catch (err) {
        save.disabled = false;
        if (!(err instanceof AuthError)) { status.className = "draft-status err"; status.textContent = err.message; }
      }
    });
    return { form, disable: () => { for (const f of form.querySelectorAll("input, button")) f.disabled = true; } };
  }

  function employeeCard(e) {
    const company = currentCompany();
    const url = `/companies/${company.id}/employees/${e.id}`;
    if (editing === e.id) {
      const { form } = employeeForm(e, async (v) => {
        await api(url, { method: "PUT", body: v });
        editing = null; changed();
      }, () => { editing = null; render(); }, t("common.save"), true);
      return el("section", { class: "panel" }, el("h2", { text: e.full_name }), form);
    }
    const when = e.terminated_on ? t("emp.left", { date: shortDate(e.terminated_on) }) : t("emp.since", { date: shortDate(e.hired_on) });
    return el("section", { class: "panel entity" + (e.terminated_on ? " left" : "") },
      el("div", { class: "entity-head" },
        el("span", { class: "entity-mark", "aria-hidden": "true", style: `--c:var(--c-${tint(e.full_name)})`, text: initialsOf(e.full_name) }),
        el("div", { class: "entity-name" }, el("b", { text: e.full_name }), el("span", { text: `${e.personal_id} · ${when}` })),
        el("span", { class: "state " + (e.pension_participant ? "info" : ""), text: t(e.pension_participant ? "emp.pensionYes" : "emp.pensionNo") }),
        el("b", { class: "emp-salary", text: gel(e.gross_monthly_salary) })),
      el("div", { class: "actions" },
        el("button", { class: "btn small", type: "button", text: t("common.edit"), onclick: () => { editing = e.id; render(); } }),
        el("button", { class: "btn small", type: "button", text: t("payments.remove"), onclick: async () => {
          if (!confirm(t("emp.removeConfirm", { name: e.full_name }))) return;
          try { await api(url, { method: "DELETE" }); } catch (err) { if (!(err instanceof AuthError)) alert(err.message); }
          changed();
        } })));
  }

  function addPanel() {
    const company = currentCompany();
    if (!adding) {
      return el("button", { class: "btn primary", type: "button", style: "justify-self:start", text: `+ ${t("hire.save")}`,
        onclick: () => { adding = true; render(); } });
    }
    const { form } = employeeForm({ hired_on: new Date().toISOString().slice(0, 10) }, async (v) => {
      await api(`/companies/${company.id}/employees`, { method: "POST", body: v });
      adding = false; changed();
    }, () => { adding = false; render(); }, t("hire.save"), false);
    return el("section", { class: "panel" }, el("h2", { text: t("hire.title") }), form);
  }

  /* ---------- the month's declaration ---------- */
  function copyButton(read) {
    const button = el("button", { class: "btn small", type: "button", text: t("books.copy") });
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(read());
        button.textContent = t("books.copied");
        setTimeout(() => { button.textContent = t("books.copy"); }, 1500);
      } catch { /* clipboard blocked: the figures stay visible to copy by hand */ }
    });
    return button;
  }

  function declaration() {
    const picker = el("input", { class: "field", type: "month", value: month, style: "width:auto", "aria-label": t("emp.month") });
    picker.addEventListener("change", () => { if (picker.value) { month = picker.value; load(); } });
    const head = el("div", { class: "panel-head" }, el("h2", { text: t("emp.declaration") }), picker);
    if (!payroll) return el("section", { class: "panel" }, head);
    const parts = [head];
    if (payroll.return_due) parts.push(el("span", { class: "state todo", style: "justify-self:start", text: t("emp.due", { date: shortDate(payroll.return_due) }) }));
    if (!payroll.lines.length) {
      parts.push(el("p", { class: "muted", style: "margin:0", text: t("emp.nobody") }));
      return el("section", { class: "panel" }, parts);
    }
    const value = (line, name) => (line.result.breakdown.find((b) => b.name === name) || {}).amount;
    const rows = payroll.lines.map((line) => {
      const gross = line.employee.gross_monthly_salary;
      return el("tr", {},
        el("td", {}, el("b", { text: line.employee.full_name }), el("div", { class: "muted", text: line.employee.personal_id })),
        ...COLUMNS.map((c) => el("td", { class: "num", text: formatAmount(c === "gross_salary" ? gross : value(line, c) ?? "0.00") })));
    });
    const totals = payroll.totals;
    rows.push(el("tr", { class: "total" }, el("td", {}, el("b", { text: t("emp.total") })),
      ...COLUMNS.map((c) => el("td", { class: "num" }, el("b", { text: formatAmount(totals[c] ?? "0.00") })))));
    const tsv = () => [
      [t("emp.col.name"), t("hire.personalId"), ...COLUMNS.map((c) => t(HEADS[c]))].join("\t"),
      ...payroll.lines.map((l) => [l.employee.full_name, l.employee.personal_id,
        ...COLUMNS.map((c) => (c === "gross_salary" ? l.employee.gross_monthly_salary : value(l, c) ?? "0.00"))].join("\t")),
    ].join("\n");
    parts.push(
      el("div", { class: "books-table-wrap" }, el("table", { class: "books-table emp-table" },
        el("thead", {}, el("tr", {}, el("th", { text: t("emp.col.name") }), ...COLUMNS.map((c) => el("th", { class: "num", text: t(HEADS[c]) })))),
        el("tbody", {}, rows))),
      el("div", { class: "actions" }, copyButton(tsv),
        el("span", { class: "grow", text: t("emp.payNote") })),
      el("div", { class: "rs-send" },
        el("div", { class: "panel-head" }, el("b", { text: t("emp.rsTitle") }), el("span", { class: "state info", text: t("bk.soon") })),
        el("p", { class: "muted", style: "margin:0;font-size:13.5px", text: t("emp.rsText") }),
        el("div", { class: "actions" },
          el("button", { class: "btn", type: "button", disabled: "", text: t("emp.rsTitle") }),
          el("a", { class: "btn primary", href: RS_PORTAL, target: "_blank", rel: "noopener noreferrer", text: `${t("emp.openRs")} ↗` }))));
    return el("section", { class: "panel" }, parts);
  }

  function render() {
    if (!open) return;
    const head = el("div", { class: "page-head" }, el("div", {}, el("h1", { text: t("nav.employees") }), el("p", { text: t("emp.desc") })));
    if (!list) { $("employeesInner").replaceChildren(head); return; }
    const people = list.length ? el("div", { class: "emp-people" }, list.map(employeeCard))
      : el("section", { class: "panel" }, el("p", { class: "muted", style: "margin:0", text: t("emp.none") }));
    $("employeesInner").replaceChildren(head, people, addPanel(), declaration());
  }

  /* ---------- the chat's card ---------- */
  // Nothing is saved until the user fills in the name and personal number and presses Save.
  function hireCard(d, live) {
    const values = { gross_monthly_salary: d.gross_monthly_salary, hired_on: d.hired_on, pension_participant: d.pension_participant };
    const status = el("p", { class: "draft-status", role: "status" });
    let built;
    const finish = (text, ok) => {
      built.disable();
      for (const b of built.form.querySelectorAll(".actions button")) b.remove();
      status.className = "draft-status " + (ok ? "ok" : "");
      status.replaceChildren(el("span", { text }),
        ok ? el("button", { class: "link-btn", type: "button", text: t("hire.open"), onclick: () => go("employees") }) : null);
    };
    built = employeeForm(values, async (v) => {
      await api(`/companies/${currentCompany().id}/employees`, { method: "POST", body: v });
      finish(t("hire.saved"), true);
      changed();
    }, () => finish(t("hire.dropped"), false), t("hire.save"), false);
    if (!live) built.disable();
    return el("div", { class: "draft-card hire-card" },
      el("div", { class: "draft-head" }, el("strong", { text: t("hire.title") }),
        d.net_monthly_salary ? el("span", { class: "draft-currency", text: t("hire.netNote", { amount: gel(d.net_monthly_salary) }) }) : null),
      built.form, status);
  }

  window.Employees = {
    show() {
      open = true; month = month || thisMonth(); $("employees").hidden = false; render(); load();
    },
    hide() { open = false; adding = false; editing = null; },
    reload() { if (open) load(); },
    onCompanyChange() { list = null; payroll = null; adding = false; editing = null; if (open) { render(); load(); } },
    onLanguageChange() { render(); },
    hireCard,
  };
})();
