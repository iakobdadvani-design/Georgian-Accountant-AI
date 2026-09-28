/* Tax payments: the bank a company pays from, what's due with amounts, and what's been paid; plus the "Pay" dialog
   used here and next to each deadline. Paying happens in the customer's own internet bank: the dialog shows the
   treasury transfer details to copy and opens their bank. The app never signs in to a bank or moves money.
   Uses the page's helpers ($, el, t, tp, loc, api, formatAmount, monthYear, shortDate, currentCompany,
   deadlineItems, loadDeadlines, AuthError). */
(() => {
  const gel = (value) => `${formatAmount(value)} ${t("card.currency")}`;

  let open = false;
  let details = null;   // treasury code, bank code, banks
  let bank = null;      // this company's saved bank, or null
  let history = [];
  let editing = false;  // choosing a bank
  let picked = null;    // bank id chosen in the form
  let current = null;   // deadline being paid
  let loadToken = 0;

  /* ---------- shared ---------- */
  async function getDetails() {
    if (!details) details = await api("/payments");
    return details;
  }

  const bankInfo = (id) => details && details.banks.find((b) => b.id === id);

  function periodLabel(d) {
    return d.period_start.slice(0, 7) === d.period_end.slice(0, 7) ? monthYear(d.period_start) : d.period_start.slice(0, 4);
  }

  function whenText(d) {
    const left = d.days_left < 0 ? tp("deadlines.overdue", -d.days_left)
      : d.days_left === 0 ? t("deadlines.today") : d.days_left === 1 ? t("deadlines.tomorrow") : tp("deadlines.inDays", d.days_left);
    return `${t("deadlines.by", { date: shortDate(d.due_date) })} · ${left}`;
  }

  const formatIban = (iban) => iban.replace(/(.{4})/g, "$1 ").trim();

  // "1 234,56", "1,234.56", "900" -> "1234.56"; null if it isn't an amount with at most two decimals.
  function parseAmount(text) {
    let s = text.replace(/[\s\u00a0\u202f]/g, "");
    const last = Math.max(s.lastIndexOf(","), s.lastIndexOf("."));
    if (last >= 0 && s.length - last - 1 <= 2) s = s.slice(0, last).replace(/[.,]/g, "") + "." + s.slice(last + 1);
    else s = s.replace(/[.,]/g, "");
    return /^\d+(\.\d{1,2})?$/.test(s) ? s : null;
  }

  function copyButton(read) {
    const button = el("button", { class: "btn small copy", type: "button", text: t("books.copy") });
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(read());
        button.textContent = t("books.copied");
        setTimeout(() => { button.textContent = t("books.copy"); }, 1500);
      } catch { /* clipboard blocked; the value is on screen */ }
    });
    return button;
  }

  function openBankLink(info, cls = "btn") {
    return el("a", { class: `${cls} bank-open`, href: info.url, target: "_blank", rel: "noopener noreferrer",
      style: `--bank:${info.color}`, text: t("pay.openIn", { bank: t(`bank.${info.id}`) }) });
  }

  /* ---------- screen ---------- */
  function show() {
    if (!currentCompany()) return;
    window.Books?.hide();
    window.Reviews?.hide();
    open = true;
    document.body.classList.add("payments-open");
    $("payments").hidden = false;
    $("app").classList.remove("drawer-open");
    $("title").textContent = t("payments.nav") + " · " + currentCompany().name;
    load();
  }

  function hide() {
    if (!open) return;
    open = false;
    editing = false;
    document.body.classList.remove("payments-open");
    $("payments").hidden = true;
    const company = currentCompany();
    if (company) $("title").textContent = company.name;
  }

  async function load() {
    const company = currentCompany();
    if (!company) return;
    const token = ++loadToken;
    try {
      const [, saved, paid] = await Promise.all([getDetails(), api(`/companies/${company.id}/bank`),
        api(`/companies/${company.id}/payments/history`)]);
      if (token !== loadToken) return;
      bank = saved;
      history = paid;
    } catch (err) {
      if (err instanceof AuthError) return;
      bank = null;
      history = [];
    }
    render();
  }

  function render() {
    if (!open || !details) return;
    $("paymentsInner").replaceChildren(bankCard(), dueCard(), historyCard());
  }

  function bankCard() {
    const card = el("section", { class: "pay-card" }, el("h3", { text: t("payments.bank") }));
    const info = bank && bankInfo(bank.bank_id);
    if (info && !editing) {
      card.append(
        el("div", { class: "bank-linked", style: `--bank:${info.color}` },
          el("div", { class: "bank-text" },
            el("span", { class: "bank-name", text: t(`bank.${info.id}`) }),
            bank.iban ? el("span", { class: "bank-iban", text: formatIban(bank.iban) }) : null),
          el("div", { class: "books-actions" },
            openBankLink(info, "btn primary"),
            el("button", { class: "btn", type: "button", text: t("payments.change"),
              onclick: () => { editing = true; picked = bank.bank_id; render(); } }),
            el("button", { class: "btn", type: "button", text: t("payments.remove"), onclick: removeBank }))),
        el("p", { class: "hint-text", text: t("payments.linkedNote") }));
      return card;
    }
    const error = el("p", { class: "rs-note err", role: "alert" });
    const iban = el("input", { class: "field", id: "bankIban", autocomplete: "off", spellcheck: "false",
      placeholder: "GE00 TB00 0000 0000 0000 00" });
    if (editing && bank && bank.bank_id === picked && bank.iban) iban.value = formatIban(bank.iban);
    const tiles = el("div", { class: "pay-banks", role: "group", "aria-label": t("payments.bank") },
      ...details.banks.map((b) => el("button", { class: "bank-tile", type: "button", style: `--bank:${b.color}`,
        "aria-pressed": String(picked === b.id), text: t(`bank.${b.id}`),
        onclick: (e) => { picked = b.id; for (const x of tiles.children) x.setAttribute("aria-pressed", String(x === e.currentTarget)); } })));
    const form = el("form", { class: "bank-form", novalidate: "" },
      el("p", { class: "hint-text", text: t("payments.bankDesc") }),
      tiles,
      el("label", {}, el("span", { text: t("payments.iban") }), iban),
      error,
      el("div", { class: "books-actions" },
        el("button", { class: "btn primary", type: "submit", text: t("payments.save") }),
        bank ? el("button", { class: "btn", type: "button", text: t("common.cancel"),
          onclick: () => { editing = false; render(); } }) : null));
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!picked) { error.textContent = t("payments.chooseBank"); return; }
      try {
        bank = await api(`/companies/${currentCompany().id}/bank`, { method: "PUT",
          body: { bank_id: picked, iban: iban.value.trim() || null } });
        editing = false;
        render();
      } catch (err) {
        if (err instanceof AuthError) return;
        error.textContent = /iban/i.test(err.message) ? t("payments.ibanBad") : err.message;
      }
    });
    card.append(form);
    return card;
  }

  async function removeBank() {
    if (!confirm(t("payments.removeConfirm"))) return;
    try {
      await api(`/companies/${currentCompany().id}/bank`, { method: "DELETE" });
    } catch (err) {
      if (!(err instanceof AuthError)) alert(err.message);
      return;
    }
    bank = null;
    picked = null;
    render();
  }

  function dueCard() {
    const due = deadlineItems.filter((d) => d.payment && d.state !== "done")
      .sort((a, b) => a.days_left - b.days_left || loc(a.title).localeCompare(loc(b.title)));
    const card = el("section", { class: "pay-card" }, el("h3", { text: t("payments.toPay") }));
    if (!due.length) {
      card.append(el("p", { class: "pay-empty", text: t("payments.nothing") }));
      return card;
    }
    // One group per due date: the date and how far off it is, then each tax due that day.
    const groups = new Map();
    for (const d of due) groups.set(d.due_date, [...(groups.get(d.due_date) || []), d]);
    for (const items of groups.values()) {
      card.append(el("div", { class: `pay-group ${items[0].state}` },
        el("div", { class: "pay-group-head", text: whenText(items[0]) }),
        ...items.map((d) => el("div", { class: "pay-row" },
          el("div", { class: "r-title", text: `${loc(d.title)} · ${periodLabel(d)}` }),
          d.amount_due != null ? el("span", { class: "r-amount", text: gel(d.amount_due) })
            : el("span", { class: "r-amount none", text: t("payments.noAmount") }),
          el("button", { class: "btn small", type: "button", text: t("deadlines.pay"), onclick: () => openDialog(d) })))));
    }
    return card;
  }

  function historyCard() {
    const list = history.length ? el("div", { class: "pay-list" }, ...history.map((h) => el("div", { class: "pay-row paid" },
      el("div", {},
        el("div", { class: "r-title", text: `${loc(h.title)} · ${periodLabel(h)}` }),
        h.paid_on ? el("div", { class: "r-when", text: t("payments.paidOn", { date: fullDate(new Date(`${h.paid_on}T00:00`)) }) }) : null),
      el("span", { class: "r-amount", text: gel(h.amount) }))))
      : el("p", { class: "pay-empty", text: t("payments.noHistory") });
    return el("section", { class: "pay-card" }, el("h3", { text: t("payments.history") }), list);
  }

  /* ---------- dialog ---------- */
  function renderDialog() {
    const company = currentCompany();
    const amount = $("payAmount");
    const line = (label, value) => el("div", { class: "return-line" }, el("span", { text: label }),
      el("strong", { text: value }), copyButton(() => value));
    $("payDetails").replaceChildren(
      line(t("pay.treasuryCode"), details.treasury_code),
      line(t("pay.bankCode"), details.bank_code),
      line(t("pay.payerId"), company.tax_id),
      line(t("pay.payerName"), company.name),
      el("div", { class: "return-line" }, el("span", { text: t("pay.amount") }), el("strong", { id: "payAmountEcho" }),
        copyButton(() => parseAmount(amount.value) || amount.value)));
    echo();
    const info = bank && bankInfo(bank.bank_id);
    $("payBank").replaceChildren(...(info
      ? [openBankLink(info, "btn primary"), bank.iban ? el("p", { class: "hint-text", text: formatIban(bank.iban) }) : null]
      : [el("p", { class: "hint-text", text: t("pay.noBank") }),
         el("button", { class: "btn", type: "button", text: t("pay.linkBank"),
           onclick: () => { $("payDialog").close(); editing = true; picked = null; show(); } })]).filter(Boolean));
  }

  function echo() {
    const value = parseAmount($("payAmount").value);
    $("payAmountEcho").textContent = value ? gel(value) : "—";
  }

  async function openDialog(item) {
    const company = currentCompany();
    try {
      await getDetails();
      if (!open) bank = await api(`/companies/${company.id}/bank`);
    } catch (err) {
      if (!(err instanceof AuthError)) alert(err.message);
      return;
    }
    current = item;
    $("payTitle").textContent = `${loc(item.title)} · ${periodLabel(item)}`;
    $("payDue").textContent = whenText(item);
    $("payDue").className = `pay-due ${item.state}`;
    $("payAmount").value = item.amount_due != null ? formatAmount(item.amount_due) : "";
    $("payAmountHint").textContent = item.amount_due != null
      ? t("pay.fromBooks", { month: monthYear(item.period_start) }) : t("pay.enterAmount");
    $("payError").textContent = "";
    renderDialog();
    $("payDialog").showModal();
  }

  async function markPaid(e) {
    e.preventDefault();
    const amount = parseAmount($("payAmount").value);
    if (!amount) {
      $("payError").textContent = t("pay.badAmount");
      $("payAmount").focus();
      return;
    }
    try {
      await api(`/companies/${currentCompany().id}/deadlines/${current.deadline_id}/${current.period_start}?as_of=${$("asOf").value}`,
        { method: "PUT", body: { done: true, paid_amount: amount } });
    } catch (err) {
      if (!(err instanceof AuthError)) $("payError").textContent = err.message;
      return;
    }
    $("payDialog").close();
    await loadDeadlines();
    if (open) load();
  }

  $("payAmount").addEventListener("input", echo);
  $("payForm").addEventListener("submit", markPaid);
  $("payCancel").addEventListener("click", () => $("payDialog").close());
  $("paymentsBtn").addEventListener("click", () => (open ? hide() : show()));

  window.Pay = {
    open: openDialog, show, hide,
    get isOpen() { return open; },
    onCompanyChange() { bank = null; history = []; editing = false; picked = null; if (open) load(); },
    onDeadlines() { render(); },
    onLanguageChange() {
      if (open) { $("title").textContent = t("payments.nav") + " · " + (currentCompany() || {}).name; render(); }
      if ($("payDialog").open && current) {
        $("payTitle").textContent = `${loc(current.title)} · ${periodLabel(current)}`;
        $("payDue").textContent = whenText(current);
        renderDialog();
      }
    },
  };
})();
