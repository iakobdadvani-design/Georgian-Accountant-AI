/* Paying a deadline: the treasury transfer details to type into the customer's own internet bank, links to the
   banks, and "I've paid", which marks the deadline done with the amount. The app never moves money.
   Uses the page's helpers ($, el, t, api, formatAmount, monthYear, currentCompany, loadDeadlines). */
(() => {
  let details = null;
  let current = null;

  async function getDetails() {
    if (!details) details = await api("/payments");
    return details;
  }

  // "1 234,56", "1,234.56", "900" -> "1234.56"; null if it isn't an amount with at most two decimals.
  function parseAmount(text) {
    let s = text.replace(/[\s  ]/g, "");
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

  function line(label, value) {
    return el("div", { class: "return-line" }, el("span", { text: label }), el("strong", { text: value }),
      copyButton(() => value));
  }

  function render() {
    const company = currentCompany();
    const amount = $("payAmount");
    const amountLine = el("div", { class: "return-line" }, el("span", { text: t("pay.amount") }),
      el("strong", { id: "payAmountEcho" }), copyButton(() => parseAmount(amount.value) || amount.value));
    $("payDetails").replaceChildren(
      line(t("pay.treasuryCode"), details.treasury_code),
      line(t("pay.bankCode"), details.bank_code),
      line(t("pay.payerId"), company.tax_id),
      line(t("pay.payerName"), company.name),
      amountLine);
    echo();
    $("payBanks").replaceChildren(...details.banks.map((b) => el("a", {
      class: "bank-tile", href: b.url, target: "_blank", rel: "noopener noreferrer", style: `--bank:${b.color}`,
      text: t(`bank.${b.id}`) })));
  }

  function echo() {
    const value = parseAmount($("payAmount").value);
    $("payAmountEcho").textContent = value ? `${formatAmount(value)} ${t("card.currency")}` : "—";
  }

  async function open(item, period) {
    try {
      await getDetails();
    } catch (err) {
      if (!(err instanceof AuthError)) alert(err.message);
      return;
    }
    current = item;
    $("payTitle").textContent = `${loc(item.title)} · ${period}`;
    $("payAmount").value = item.amount_due != null ? formatAmount(item.amount_due) : "";
    $("payAmountHint").textContent = item.amount_due != null
      ? t("pay.fromBooks", { month: monthYear(item.period_start) }) : t("pay.enterAmount");
    $("payError").textContent = "";
    render();
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
    loadDeadlines();
  }

  $("payAmount").addEventListener("input", echo);
  $("payForm").addEventListener("submit", markPaid);
  $("payCancel").addEventListener("click", () => $("payDialog").close());

  window.Pay = { open };
})();
