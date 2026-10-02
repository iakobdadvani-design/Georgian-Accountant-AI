# Topic 10 — Non-residents and international (verified 2026-10-02)

ChatGPT files `Desktop\Tax knowledge base\topic-10-part-00…09, 99.md`: 87 rules (Tax Code Art. 2(7), 29, 104, 124–129¹);
every quote found in the current Tax Code by `python -m tools.kb_check`. Rates and withholding for non-residents are
in Topics 2, 3 and 5 (ChatGPT cross-referenced them rather than repeating).

Corrected by hand (same letter, wrong paragraph): 29(9)(ა)–(დ) (facilities that are *not* a permanent establishment)
had 29(2)(ა)–(დ)'s text (the ones that *are*), and 126(2)(ა)–(ბ) (more than 50% / practical control) had 126(1)(ა)–(ბ)'s.

Checker fix: a subparagraph quoted under its paragraph's lead-in ("9. … მხოლოდ:" then "ა) …") must come from that
paragraph. Both mistakes above are now caught automatically; no false alarms on the 1 279 rules so far (a lead-in that
appears in several articles, paragraph numbers on their own line, and table row numbers like "100 2. ბოლნისი" are handled).

| Fact | Article |
|---|---|
| A ratified tax treaty in force overrides the Tax Code | 2(7) |
| Permanent establishment: a fixed place of business, construction/installation site, resource exploration rig, an individual's base, branch/office/workshop/mine…; management by another person for **more than 3 months** | 29(1)–(2), (4) |
| Not a PE: independent broker without power to sign, only holding shares/property, seconded staff under the host's control, only controlling a Georgian company, storage/display/purchasing/preparatory use, only leasing property out (unless servicing it) | 29(5)–(9), (12) |
| PE exists from registration, delegated authority or start of representative activity; the tax authority registers it | 29(10)–(11) |
| Georgian-source income: work done in Georgia, goods supplied here, services performed here (or for Georgian property/securities, or by a resident provider unless through a foreign PE), dividends and shares of residents, interest/royalties paid by residents (PE attribution rules), rent of property used here, shares in companies > **50%** Georgian real estate, management/financial/insurance fees paid by residents, international transport/telecom; where the money is received doesn't matter | 104 |
| Foreign profit tax credited against Georgian tax on foreign income, at most the Georgian tax on it | 124 |
| Treaty relief and refunds: procedure in a Finance Minister order | 125 |
| Transfer pricing: related = > **50%** ownership or practical control (direct or indirect); arm's-length profit for cross-border related deals, deals with preferential-tax countries (always "controlled") and with one's own PE; 5 methods (CUP, resale, cost plus, TNMM, profit split), most appropriate one; explain on request; corresponding adjustment for treaty partners; advance pricing agreements binding while followed | 126–129¹ |

NEEDS ACCOUNTANT (part 99): the treaties themselves (none in the corpus), the Art. 125 refund order, transfer-pricing
orders (127(6), 129(3)), PE registration order (29(11)), the preferential-tax country list.

App relevance: low for the small-business user, except "is this payment Georgian-source?" for foreign freelancers and
services (decides the 20%/other withholding from Topic 3) and the 50% related-party test.
