/* Tax payments: the bank a company pays from, what's due with amounts, and what's been paid; plus the "Pay" dialog
   used here and next to each deadline. Paying happens in the customer's own internet bank: the dialog shows the
   treasury transfer details to copy and opens their bank. The app never signs in to a bank or moves money.
   Uses the page's helpers ($, el, t, tp, loc, api, formatAmount, monthYear, shortDate, currentCompany,
   deadlineItems, loadDeadlines, AuthError). */
(() => {
  const gel = (value) => `${formatAmount(value)} ${t("card.currency")}`;

  let open = false;
  let details = null;   // treasury code, bank code, banks
  let bank = null;      // the account taxes are paid from (Banks page), or null
  let history = [];
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
      const [, banks, paid] = await Promise.all([getDetails(), api(`/companies/${company.id}/banks`),
        api(`/companies/${company.id}/payments/history`)]);
      if (token !== loadToken) return;
      bank = primaryOf(banks);
      history = paid;
    } catch (err) {
      if (err instanceof AuthError) return;
      bank = null;
      history = [];
    }
    render();
  }

  const primaryOf = (banks) => banks.find((b) => b.is_primary) || banks[0] || null;

  function render() {
    if (!open || !details) return;
    $("paymentsInner").replaceChildren(
      el("div", { class: "page-head" }, el("div", {}, el("h1", { text: t("payments.nav") }))),
      bankLine(), dueCard(), historyCard());
  }

  // Where taxes are paid from; the accounts themselves are managed on the Banks page.
  function bankLine() {
    const info = bank && bankInfo(bank.bank_id);
    const manage = el("button", { class: "btn small", type: "button", text: t("payments.manageBanks"), onclick: () => go("banks") });
    if (!info) {
      return el("div", { class: "notice todo" }, el("span", { text: t("payments.noBankYet") }),
        el("button", { class: "btn small primary", type: "button", text: t("pay.linkBank"), onclick: () => go("banks") }));
    }
    return el("div", { class: "notice" },
      el("span", { text: t("payments.payingFrom", { bank: t(`bank.${info.id}`) + (bank.iban ? ` · ${formatIban(bank.iban)}` : "") }) }),
      openBankLink(info, "btn small"), manage);
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
           onclick: () => { $("payDialog").close(); go("banks"); } })]).filter(Boolean));
  }

  function echo() {
    const value = parseAmount($("payAmount").value);
    $("payAmountEcho").textContent = value ? gel(value) : "—";
  }

  async function openDialog(item) {
    const company = currentCompany();
    try {
      await getDetails();
      if (!open) bank = primaryOf(await api(`/companies/${company.id}/banks`));
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

  window.Pay = {
    open: openDialog, show, hide,
    get isOpen() { return open; },
    onCompanyChange() { bank = null; history = []; if (open) load(); },
    onBanksChange() { if (open) load(); else bank = null; },
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
