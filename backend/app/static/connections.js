/* Connections: companies with their tax profile and RS.ge link, and the company's bank accounts.
   RS values are shown beside the profile and change it only when the user presses "Use RS.ge value".
   Bank accounts are saved for convenience: the app never signs in to a bank.
   Uses the page's helpers ($, el, t, loc, api, formatAmount, fullDate, shortDate, companies, currentCompany, go,
   selectCompany, openCompanyDialog, openProfileDialog, loadCompanies, initialsOf, AuthError). */
(() => {
  const formatIban = (iban) => iban.replace(/(.{4})/g, "$1 ").trim();
  const yes = (b) => t(b ? "common.yes" : "common.no");
  const note = (cls = "") => el("p", { class: "rs-note " + cls, role: "status" });
  const TINTS = ["indigo", "teal", "violet", "blue", "amber", "green", "wine"];
  const tint = (name) => TINTS[[...name].reduce((h, ch) => (h * 31 + ch.codePointAt(0)) % 9973, 7) % TINTS.length];

  /* ---------- companies & RS.ge ---------- */
  let coOpen = false;
  let rows = null;        // [{ company, profile, rs }]
  let connectFor = null;  // company id whose connect form is open
  let coToken = 0;

  async function loadCompaniesView() {
    const mine = ++coToken;
    const list = companies.slice();
    const loaded = await Promise.all(list.map(async (company) => {
      const [profile, rs] = await Promise.all([
        api(`/companies/${company.id}/tax-profile`).catch(() => null),
        api(`/companies/${company.id}/rs`).catch(() => null),
      ]);
      return { company, profile, rs };
    }));
    if (mine !== coToken) return;
    rows = loaded;
    renderCompanies();
    const current = currentCompany();
    const row = current && rows.find((r) => r.company.id === current.id);
    $("companiesDot").hidden = !row || !row.rs || row.rs.connected;
  }

  function rsState(rs) {
    if (!rs || !rs.connected) return el("span", { class: "state todo" }, el("span", { class: "state-dot" }), t("co.notConnected"));
    if (rs.status === "rejected") return el("span", { class: "state bad" }, el("span", { class: "state-dot" }), t("co.rejected"));
    if (rs.status === "unreachable") return el("span", { class: "state todo" }, el("span", { class: "state-dot" }), t("co.unreachable"));
    return el("span", { class: "state good" }, el("span", { class: "state-dot" }), t("co.connected"));
  }

  async function withBusy(button, work) {
    button.disabled = true;
    try { await work(); } finally { button.disabled = false; }
  }

  function companyCard({ company, profile, rs }) {
    const connected = rs && rs.connected;
    const current = (currentCompany() || {}).id === company.id;
    const status = note();
    const vatFact = connected && rs.vat_payer !== null
      ? t("co.rsVat", { value: yes(rs.vat_payer) }) : profile ? yes(profile.vat_registered) : t("profile.notSet");
    const facts = el("div", { class: "facts" },
      [[t("profile.vat"), vatFact], [t("profile.regime"), profile ? t("regime." + profile.tax_regime) : "—"],
       [t("profile.employees"), profile ? yes(profile.has_employees) : "—"], [t("profile.property"), profile ? yes(profile.owns_property) : "—"]]
        .map(([k, v]) => el("div", { class: "fact" }, el("span", { text: k }), el("b", { text: v }))));

    const notices = [];
    if (connected && rs.status === "ok" && profile && rs.vat_payer !== null && rs.vat_payer !== profile.vat_registered) {
      const use = el("button", { class: "btn small", type: "button", text: t("co.useRsVat") });
      use.addEventListener("click", () => withBusy(use, async () => {
        await api(`/companies/${company.id}/tax-profile`, { method: "PUT", body: { ...profile, vat_registered: rs.vat_payer,
          vat_registration_date: rs.vat_payer ? profile.vat_registration_date : null } });
        afterProfileChange(company);
      }));
      notices.push(el("div", { class: "notice todo" }, el("span", { text: t("co.vatDiffers") }), use));
    }
    if (connected && rs.registered_name && rs.registered_name !== company.name) {
      const use = el("button", { class: "btn small", type: "button", text: t("co.useRsName") });
      use.addEventListener("click", () => withBusy(use, async () => {
        await api(`/companies/${company.id}`, { method: "PATCH", body: { name: rs.registered_name } });
        await loadCompanies((currentCompany() || {}).id);
      }));
      notices.push(el("div", { class: "notice" }, el("span", { text: t("co.nameDiffers", { name: rs.registered_name }) }), use));
    }

    const edit = el("button", { class: "btn small", type: "button", text: t("co.editProfile"), onclick: () => openProfileDialog(company, profile) });
    const actions = [el("span", { class: "grow", text: connected ? t("co.checked", { date: fullDate(new Date(rs.checked_at)) }) : t("co.connectHint") })];
    if (connected) {
      const recheck = el("button", { class: "btn small", type: "button", text: t("co.recheck") });
      recheck.addEventListener("click", () => withBusy(recheck, async () => {
        try {
          await api(`/companies/${company.id}/rs/check`, { method: "POST" });
          loadCompaniesView();
        } catch (err) { if (!(err instanceof AuthError)) { status.className = "rs-note err"; status.textContent = err.message; } }
      }));
      const disconnect = el("button", { class: "btn small", type: "button", text: t("co.disconnect") });
      disconnect.addEventListener("click", async () => {
        if (!confirm(t("co.disconnectConfirm", { name: company.name }))) return;
        try { await api(`/companies/${company.id}/rs`, { method: "DELETE" }); } catch (err) { if (!(err instanceof AuthError)) alert(err.message); }
        loadCompaniesView();
        window.Overview?.reload();
      });
      actions.push(recheck, edit, disconnect);
    } else {
      actions.push(el("button", { class: "btn small primary", type: "button", text: t("ov.setup.rs"),
        onclick: () => { connectFor = company.id; renderCompanies(); } }), edit);
    }

    return el("section", { class: "panel entity" + (connected ? "" : " todo") },
      el("div", { class: "entity-head" },
        el("span", { class: "entity-mark", "aria-hidden": "true", style: `--c:var(--c-${tint(company.name)})`, text: initialsOf(company.name) }),
        el("div", { class: "entity-name" }, el("b", { text: company.name }),
          el("span", { text: `${company.tax_id} · ${t("legal." + company.legal_form)}` })),
        rsState(rs),
        current ? el("span", { class: "state info", text: t("co.current") })
          : el("button", { class: "btn small", type: "button", text: t("co.select"), onclick: () => selectCompany(company.id) })),
      facts, notices, el("div", { class: "actions" }, actions), status);
  }

  function afterProfileChange(company) {
    loadCompaniesView();
    if ((currentCompany() || {}).id === company.id) { loadProfile(company); loadDeadlines(); window.Books?.onCompanyChange(); window.Overview?.reload(); }
  }

  function connectPanel(row) {
    const { company, rs } = row;
    const panel = el("section", { class: "panel" },
      el("h2", { text: t("co.connectTitle", { name: company.name }) }),
      el("p", { class: "muted", style: "margin:0", text: t("co.connectIntro") }),
      el("ol", { class: "steps-list" },
        el("li", {}, el("span", { class: "n", text: "1" }), el("span", {},
          el("a", { href: "https://eservices.rs.ge", target: "_blank", rel: "noopener noreferrer", text: t("co.step1", { site: "eservices.rs.ge" }) }))),
        el("li", {}, el("span", { class: "n", text: "2" }), el("span", { text: t("co.step2") })),
        el("li", {}, el("span", { class: "n", text: "3" }), el("span", { text: t("co.step3") }))));
    if (rs && !rs.available) {
      panel.append(el("div", { class: "notice todo" }, el("span", { text: t("co.unavailable") })));
      return panel;
    }
    const userField = el("input", { class: "field", name: "service_user", autocomplete: "off", spellcheck: "false", maxlength: "100" });
    const passField = el("input", { class: "field", name: "password", type: "password", autocomplete: "new-password", maxlength: "200" });
    const status = note();
    const submit = el("button", { class: "btn primary", type: "submit", text: t("co.connectBtn") });
    const form = el("form", { class: "stack", novalidate: "" },
      el("label", {}, el("span", { text: t("co.serviceUser") }), userField),
      el("label", {}, el("span", { text: t("auth.password") }), passField),
      status,
      el("div", { class: "actions" }, submit,
        el("button", { class: "btn", type: "button", text: t("common.cancel"), onclick: () => { connectFor = null; renderCompanies(); } })),
      el("div", { class: "notice good" }, el("span", { text: t("co.secure") })));
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!userField.value.trim() || !passField.value) { status.className = "rs-note err"; status.textContent = t("companyDialog.required"); return; }
      submit.disabled = true;
      status.className = "rs-note"; status.textContent = t("co.checking");
      try {
        await api(`/companies/${company.id}/rs`, { method: "PUT", body: { service_user: userField.value.trim(), password: passField.value } });
        passField.value = "";
        connectFor = null;
        loadCompaniesView();
        window.Overview?.reload();
      } catch (err) {
        if (!(err instanceof AuthError)) { status.className = "rs-note err"; status.textContent = err.message; }
      } finally {
        submit.disabled = false;
      }
    });
    panel.append(form);
    setTimeout(() => userField.focus(), 0);
    return panel;
  }

  function renderCompanies() {
    if (!coOpen) return;
    const head = el("div", { class: "page-head" },
      el("div", {}, el("h1", { text: t("nav.companies") }), el("p", { text: t("co.desc") })),
      el("button", { class: "btn", type: "button", text: t("co.add"), onclick: openCompanyDialog }));
    if (!rows) { $("companiesInner").replaceChildren(head); return; }
    const target = rows.find((r) => r.company.id === connectFor);
    $("companiesInner").replaceChildren(head, el("div", { class: "two-col" },
      el("div", { class: "stack" }, rows.length ? rows.map(companyCard)
        : el("section", { class: "panel" }, el("p", { class: "muted", text: t("welcome.desc") }))),
      target ? connectPanel(target) : null));
  }

  window.Companies = {
    show() { coOpen = true; $("companies").hidden = false; renderCompanies(); loadCompaniesView(); },
    hide() { coOpen = false; connectFor = null; },
    render() { renderCompanies(); },
    reload() { loadCompaniesView(); },
    onCompanyChange() { loadCompaniesView(); },
    onLanguageChange() { renderCompanies(); },
  };

  /* ---------- banks ---------- */
  let bkOpen = false;
  let banks = null;
  let catalog = null;   // /payments: bank ids, colours, internet-bank links
  let adding = null;    // { bank_id } while choosing a new account
  let editing = null;   // account id being edited
  let bkToken = 0;

  const info = (id) => catalog && catalog.banks.find((b) => b.id === id);

  async function loadBanks() {
    const company = currentCompany();
    if (!company) return;
    const mine = ++bkToken;
    try {
      const [cat, list] = await Promise.all([catalog ? catalog : api("/payments"), api(`/companies/${company.id}/banks`)]);
      if (mine !== bkToken) return;
      catalog = cat; banks = list;
    } catch (err) {
      if (err instanceof AuthError) return;
      banks = [];
    }
    renderBanks();
  }

  function changed() {
    loadBanks();
    window.Pay?.onBanksChange();
    window.Overview?.reload();
  }

  function accountForm(values, onSave, onCancel, saveText) {
    const iban = el("input", { class: "field", autocomplete: "off", spellcheck: "false", placeholder: "GE00 TB00 0000 0000 0000 00",
      value: values.iban ? formatIban(values.iban) : "" });
    const currency = el("select", { class: "field" }, ["GEL", "USD", "EUR", "GBP"].map((c) =>
      el("option", { value: c, text: c, selected: c === (values.currency || "GEL") ? "true" : null })));
    const primary = el("input", { type: "checkbox", checked: values.is_primary ? "true" : null });
    const status = note();
    const form = el("form", { class: "stack", novalidate: "" },
      el("div", { class: "form-row" },
        el("label", {}, el("span", { text: t("payments.iban") }), iban),
        el("label", {}, el("span", { text: t("bk.currency") }), currency)),
      el("label", { class: "check", style: "display:flex;align-items:center;gap:8px;font-weight:400" }, primary, el("span", { text: t("bk.makePrimary") })),
      status,
      el("div", { class: "actions" }, el("button", { class: "btn primary", type: "submit", text: saveText }),
        el("button", { class: "btn", type: "button", text: t("common.cancel"), onclick: onCancel })));
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await onSave({ iban: iban.value.trim() || null, currency: currency.value, is_primary: primary.checked });
      } catch (err) {
        if (!(err instanceof AuthError)) { status.className = "rs-note err"; status.textContent = err.message; }
      }
    });
    return form;
  }

  function bankCard(account) {
    const b = info(account.bank_id) || { id: account.bank_id, color: "#5b6270", url: null, logo: null };
    const company = currentCompany();
    const url = `/companies/${company.id}/banks/${account.id}`;
    const body = editing === account.id
      ? [accountForm(account, async (v) => {
          await api(url, { method: "PUT", body: { bank_id: account.bank_id, ...v, is_primary: v.is_primary || account.is_primary } });
          editing = null; changed();
        }, () => { editing = null; renderBanks(); }, t("common.save"))]
      : [
          el("div", { class: "notice" + (account.last_import_at ? " good" : " todo") }, el("span", {
            text: account.last_import_at ? t("bk.lastImport", { date: shortDate(account.last_import_at), count: tp("books.count", account.last_import_count || 0) })
              : t("bk.noImport") })),
          el("div", { class: "actions" },
            b.url ? el("a", { class: "btn" + (account.is_primary ? " primary" : ""), href: b.url, target: "_blank", rel: "noopener noreferrer",
              text: `${t("bk.openBank")} ↗` }) : null,
            el("button", { class: "btn", type: "button", text: t("bk.upload"), onclick: () => window.Books?.openImport(account.id, account.currency) }),
            account.is_primary ? null : el("button", { class: "btn small", type: "button", text: t("bk.makePrimary"), onclick: async () => {
              await api(url, { method: "PUT", body: { bank_id: account.bank_id, iban: account.iban, currency: account.currency, is_primary: true } });
              changed();
            } }),
            el("button", { class: "btn small", type: "button", text: t("common.edit"), onclick: () => { editing = account.id; renderBanks(); } }),
            el("button", { class: "btn small", type: "button", text: t("payments.remove"), onclick: async () => {
              if (!confirm(t("bk.removeConfirm", { bank: t(`bank.${b.id}`) }))) return;
              try { await api(url, { method: "DELETE" }); } catch (err) { if (!(err instanceof AuthError)) alert(err.message); }
              changed();
            } })),
        ];
    return el("section", { class: "panel entity" },
      el("div", { class: "entity-head" },
        b.logo ? el("img", { class: "bank-mark", src: b.logo, alt: "", width: "48", height: "48" }) : null,
        el("div", { class: "entity-name" }, el("b", { text: t(`bank.${b.id}`) }),
          el("span", { text: [account.iban ? formatIban(account.iban) : null, account.currency].filter(Boolean).join(" · ") })),
        account.is_primary ? el("span", { class: "state bad", text: t("bk.primary") }) : null),
      body);
  }

  function addCard() {
    const company = currentCompany();
    const pick = el("div", { class: "bank-pick", role: "group", "aria-label": t("bk.add") }, catalog.banks.map((b) =>
      el("button", { type: "button", style: `--bank:${b.color}`, "aria-pressed": String(adding && adding.bank_id === b.id),
        onclick: () => { adding = { bank_id: b.id }; renderBanks(); } },
        el("img", { class: "bank-logo", src: b.logo, alt: "", width: "26", height: "26" }), el("span", { text: t(`bank.${b.id}`) }))));
    const parts = [el("h2", { text: t("bk.add") }), pick];
    if (adding) {
      parts.push(accountForm({ is_primary: !banks.length }, async (v) => {
        await api(`/companies/${company.id}/banks`, { method: "POST", body: { bank_id: adding.bank_id, ...v } });
        adding = null; changed();
      }, () => { adding = null; renderBanks(); }, t("bk.save")));
    }
    return el("section", { class: "panel" }, parts);
  }

  function renderBanks() {
    if (!bkOpen) return;
    const head = el("div", { class: "page-head" }, el("div", {}, el("h1", { text: t("nav.banks") }), el("p", { text: t("bk.desc") })));
    if (!banks || !catalog) { $("banksInner").replaceChildren(head); return; }
    const primary = banks.find((b) => b.is_primary);
    const upload = el("button", { class: "dropzone", type: "button", onclick: () => window.Books?.openImport(primary ? primary.id : null, primary ? primary.currency : "GEL") },
      uploadIcon(), el("b", { text: t("bk.drop") }), el("span", { text: t("bk.dropHint") }));
    $("banksInner").replaceChildren(head, el("div", { class: "two-col" },
      el("div", { class: "stack" },
        banks.length ? banks.map(bankCard) : el("section", { class: "panel" }, el("p", { class: "muted", style: "margin:0", text: t("bk.none") })),
        addCard()),
      el("div", { class: "stack" },
        el("section", { class: "panel" }, el("h2", { text: t("ov.setup.statement") }), upload),
        el("section", { class: "panel" },
          el("div", { class: "panel-head" }, el("h2", { text: t("bk.directTitle") }), el("span", { class: "state info", text: t("bk.soon") })),
          el("p", { class: "muted", style: "margin:0;font-size:13.5px", text: t("bk.directText") })))));
  }

  function uploadIcon() {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    for (const [k, v] of Object.entries({ width: 28, height: 28, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
      "stroke-width": 1.9, "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" })) svg.setAttribute(k, v);
    const path = document.createElementNS(ns, "path");
    path.setAttribute("d", "M12 15V3M7 8l5-5 5 5M4 17v3h16v-3");
    svg.append(path);
    return svg;
  }

  window.Banks = {
    show() { bkOpen = true; $("banks").hidden = false; renderBanks(); loadBanks(); },
    hide() { bkOpen = false; adding = null; editing = null; },
    reload() { if (bkOpen) loadBanks(); },
    onCompanyChange() { banks = null; adding = null; editing = null; if (bkOpen) loadBanks(); },
    onLanguageChange() { renderBanks(); },
  };
})();
