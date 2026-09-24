/* Rule review: every rule and deadline the app uses, its legal source and sign-off status.
   Listed reviewers (REVIEWER_EMAILS) approve or request changes; the server ties each decision to the exact
   content it was made on. Uses the page's helpers ($, el, t, loc, api, store, currentCompany). */
(() => {
  const OPS = { eq: "=", ne: "≠", gt: ">", gte: "≥", lt: "<", lte: "≤" };
  const STEP_OPS = { multiply: "×", divide: "÷", subtract: "−", add: "+" };

  let open = false;
  let data = null;
  let filter = "open";
  let error = "";

  function show() {
    window.Books?.hide();
    open = true;
    document.body.classList.add("reviews-open");
    $("reviews").hidden = false;
    $("app").classList.remove("drawer-open");
    $("title").textContent = t("review.title");
    load();
  }

  function hide() {
    if (!open) return;
    open = false;
    document.body.classList.remove("reviews-open");
    $("reviews").hidden = true;
    const company = currentCompany();
    $("title").textContent = company ? company.name : t("noCompany.title");
  }

  async function load() {
    try {
      data = await api("/reviews");
      error = "";
    } catch (err) {
      if (err instanceof AuthError) return;
      error = err.message;
    }
    render();
  }

  const isoDate = (iso) => (iso ? shortDate(iso) + " " + iso.slice(0, 4) : "");

  function conditionLines(condition, depth = 0) {
    if (!condition) return [];
    if (condition.all || condition.any) {
      const children = (condition.all || condition.any).flatMap((c) => conditionLines(c, depth + 1));
      if (depth === 0 && condition.all) return children;
      return [el("li", { class: "cond-group", text: t(condition.all ? "review.allOf" : "review.anyOf") }),
        el("ul", { class: "cond-list" }, children)];
    }
    return [el("li", {},
      el("code", { text: `${condition.fact} ${OPS[condition.op] || condition.op} ${JSON.stringify(condition.value)}` }),
      condition.if_false ? el("div", { class: "cond-why", text: t("review.ifFalse") + " " + loc(condition.if_false) }) : null)];
  }

  function stepLines(calculation) {
    if (!calculation) return null;
    if (calculation.type === "percentage") return el("p", {}, el("code", { text: `${calculation.base} × ${calculation.rate}` }));
    if (calculation.type === "fixed") return el("p", {}, el("code", { text: String(calculation.amount) }));
    return el("ol", { class: "step-list" }, calculation.steps.map((s) => el("li", {},
      el("strong", { text: loc(s.label) }), " ",
      el("code", { text: `${s.name} = ${s.op === "max" ? `max(${s.args.join(", ")})` : s.args.join(` ${STEP_OPS[s.op]} `)}${s.round === false ? "" : " → 0.01"}` }),
      s.when ? el("div", { class: "cond-why" }, t("review.onlyWhen") + " ", el("code", {
        text: `${s.when.fact} ${OPS[s.when.op]} ${JSON.stringify(s.when.value)}` })) : null,
      s.name === calculation.result ? el("span", { class: "tag income", text: t("review.result") }) : null)));
  }

  function scheduleLine(schedule) {
    if (!schedule) return null;
    if (schedule.type === "monthly") return t("review.schedule.monthly", { day: schedule.day });
    const month = lookup("date.monthsGenitive")[schedule.month - 1];
    return t("review.schedule.annual", { date: t("date.short", { day: schedule.day, month }), period: t(`review.period.${schedule.period}`) });
  }

  function reviewForm(item) {
    const credentials = el("input", { class: "field", maxlength: "255", value: store.get("reviewCredentials") || "",
                                      placeholder: t("review.credentialsHint") });
    const notes = el("textarea", { class: "field", rows: "2", maxlength: "4000", placeholder: t("review.notesHint") });
    const message = el("p", { class: "form-error", role: "alert" });
    const send = async (decision) => {
      if (credentials.value.trim().length < 3) { message.textContent = t("review.needCredentials"); return; }
      store.set("reviewCredentials", credentials.value.trim());
      try {
        const updated = await api(`/reviews/${item.kind}/${encodeURIComponent(item.item_id)}/${item.version}`, {
          method: "POST", body: { decision, credentials: credentials.value.trim(), notes: notes.value, content_hash: item.content_hash } });
        data.items = data.items.map((i) => (i.kind === updated.kind && i.item_id === updated.item_id && i.version === updated.version ? updated : i));
        render();
      } catch (err) {
        if (!(err instanceof AuthError)) message.textContent = err.message;
      }
    };
    return el("div", { class: "review-form" },
      el("label", {}, el("span", { text: t("review.credentials") }), credentials),
      el("label", {}, el("span", { text: t("review.notes") }), notes),
      message,
      el("div", { class: "dialog-actions" },
        el("button", { class: "btn", type: "button", text: t("review.requestChanges"), onclick: () => send("changes_requested") }),
        el("button", { class: "btn primary", type: "button", text: t("review.approve"), onclick: () => send("approved") })));
  }

  function itemPanel(item) {
    const c = item.content;
    const source = item.legal_source;
    const range = item.effective_from ? (item.effective_to
      ? t("review.effectiveRange", { from: isoDate(item.effective_from), to: isoDate(item.effective_to) })
      : t("review.effective", { from: isoDate(item.effective_from) })) : null;
    const history = item.history.length ? el("div", { class: "review-history" },
      el("h4", { text: t("review.history") }),
      el("ul", {}, item.history.map((h) => el("li", {},
        el("span", { class: `badge ${h.decision === "approved" ? "verified" : "unverified"}`, text: t(`review.decision.${h.decision}`) }),
        " ", t("review.by", { name: h.reviewer_name, credentials: h.reviewer_credentials, date: isoDate(h.created_at) }),
        h.content_hash !== item.content_hash ? el("em", { class: "books-muted small", text: " " + t("review.olderVersion") }) : null,
        h.notes ? el("div", { class: "cond-why", text: h.notes }) : null)))) : null;
    return el("details", { class: `review-item ${item.status}` },
      el("summary", {},
        el("span", { class: "review-kind", text: t(`review.kind.${item.kind}`) }),
        el("span", { class: "review-title", text: loc(item.title) }),
        el("span", { class: `review-status ${item.status}`, text: t(`review.status.${item.status}`) })),
      el("div", { class: "review-body" },
        el("p", { class: "review-meta" },
          el("a", { href: source.url, target: "_blank", rel: "noopener", text: loc(source.citation) }),
          range ? " · " + range : "", item.version > 1 ? " · v" + item.version : ""),
        source.note ? el("div", {}, el("h4", { text: t("review.note") }), el("p", { class: "books-muted", text: source.note })) : null,
        c.conditions ? el("div", {}, el("h4", { text: t("review.conditions") }), el("ul", { class: "cond-list" }, conditionLines(c.conditions))) : null,
        c.applies ? el("div", {}, el("h4", { text: t("review.appliesTo") }), el("ul", { class: "cond-list" }, conditionLines(c.applies))) : null,
        c.calculation ? el("div", {}, el("h4", { text: t("review.steps") }), stepLines(c.calculation)) : null,
        c.schedule ? el("div", {}, el("h4", { text: t("review.schedule") }), el("p", { text: scheduleLine(c.schedule) })) : null,
        c.message ? el("div", {}, el("h4", { text: t("review.message") }), el("p", { class: "books-muted", text: loc(c.message) })) : null,
        el("details", { class: "raw" }, el("summary", { text: t("review.showRaw") }),
          el("pre", { text: JSON.stringify(c, null, 2) })),
        history,
        data.can_review ? reviewForm(item) : null));
  }

  function render() {
    if (!open) return;
    const parts = [];
    parts.push(el("div", { class: "books-head" },
      el("div", {}, el("h3", { class: "review-heading", text: t("review.title") }),
        el("p", { class: "books-muted", text: t("review.desc") })),
      data ? el("div", { class: "books-actions" },
        el("button", { class: "btn" + (filter === "open" ? " primary" : ""), type: "button", text: t("review.filter.open"),
                       onclick: () => { filter = "open"; render(); } }),
        el("button", { class: "btn" + (filter === "all" ? " primary" : ""), type: "button", text: t("review.filter.all"),
                       onclick: () => { filter = "all"; render(); } })) : null));
    if (error) parts.push(el("p", { class: "form-error", text: error }));
    if (data) {
      const verified = data.items.filter((i) => i.status === "verified").length;
      parts.push(el("div", { class: "books-limit" },
        el("div", { class: "books-limit-head" }, el("span", { text: t("review.progress") }),
          el("strong", { text: t("review.counts", { verified, total: data.items.length }) })),
        el("div", { class: "books-bar" }, el("span", { style: `width:${(100 * verified / Math.max(data.items.length, 1)).toFixed(1)}%` }))));
      if (!data.can_review) parts.push(el("p", { class: "books-muted small", text: t("review.readonly") }));
      const shown = data.items.filter((i) => filter === "all" || i.status !== "verified");
      parts.push(shown.length ? el("div", { class: "review-list" }, shown.map(itemPanel))
        : el("p", { class: "books-empty", text: t("review.allDone") }));
    }
    $("reviewsInner").replaceChildren(...parts);
  }

  $("reviewsBtn").addEventListener("click", () => (open ? hide() : show()));
  window.Reviews = {
    show, hide,
    get open() { return open; },
    onLanguageChange() { if (open) { $("title").textContent = t("review.title"); render(); } },
  };
})();
