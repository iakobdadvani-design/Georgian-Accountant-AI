# Topic 5 — Profit tax (verified 2026-10-01)

ChatGPT files `Desktop\Tax knowledge base\topic-05-part-00…08, 99.md`: 64 rules, one per rate, threshold or time limit;
every Georgian quote found word for word in the current Tax Code by `python -m tools.kb_check`, every number in a rule
backed by its quote. (Two checker fixes on the way: a zero-width space before a superscript letter, "1 მილიონ" = 1 000 000.)

The app's rule, confirmed:

| App rule | Confirmed by |
|---|---|
| `ge.profit.distribution`: payout ÷ **0.85** × **15%** — only for an ordinary distribution (not excluded by 98¹(2), no special rate or exemption) | 97(1)(ა), 97(10), 98(1), 98¹(1) |

Rates and bases:

| Fact | Article |
|---|---|
| Ordinary rate **15%**; taxable amount = payment/expense ÷ **0.85** for the 97(1)–(3) objects | 98(1), 97(10) |
| Banks, credit unions, microfinance organisations, lenders: **20%** on annual income minus deductions (this model from **1 Jan 2023**) | 98(4), 97(12), 309(94) |
| Insurance companies on the distribution model from **1 Jan 2024** | 309(94¹) |
| Slot halls and online gambling: **20%** of bets minus winnings; bets from foreign citizens online: **5%** | 98(5)–(6), 97(9¹), 97(9³) |
| Online betting (totalisator): **7%** of the month's bets, return and payment by the **15th** | 309(16) |
| Oil/gas "existing contracts" signed before **1 Jan 1998**: **10%** | 98(2) |
| International company: **5%**, taxable amount ÷ **0.95** | 23(10)–(11) |
| Banks' 2023 reserve-balance difference: **15%** | 309(134) |

What counts as distributed profit or a taxable payment:

| Fact | Article |
|---|---|
| Objects: distributed profit, non-business expenses, free supplies/money transfers, representation expenses above the limit | 97(1) |
| Representation limit: **1%** of last year's income (1% of the expense if it exceeds income; founding year: 1% of the year's expense) | 98⁴(2)–(3) |
| Not distributed profit: liquidation/buy-back up to the capital contributed; paying in own shares; dividends to the Entrepreneurs Law 2(3) persons; asset transfer to the state when it owns > **50%**; onward distribution of dividends from foreign (non-low-tax) companies | 98¹(2) |
| Deemed distributions: related-party price gaps vs market price; transfer-pricing adjustments; gaps with tax-exempt counterparties | 98¹(4) |
| Low-tax country: no profit tax, or a rate ≤ **1/3** of Georgia's; payments to such persons (loans, advances, fines, debt securities, claim losses) and loans to individuals/non-residents are taxed | 98²(3), 98²(5) |
| Non-cash payments valued at market price excluding VAT | 97(7) |
| Free supplies not taxed: charity donations ≤ **10%** of last year's net profit; free hotel stay for the room owner ≤ **60 days**; real estate to charities working ≥ **3 years** with people with disabilities | 98³(3) |

Exemptions with dates: agricultural cooperatives until **1 Jan 2028**; non-residents' interest on Georgian listed bonds
issued before **1 Jan 2028**; high-mountain enterprises **10 calendar years** from the status; special trading companies
(except gains on fixed assets used > **2 years**; other income ≤ **GEL 1 000 000** and ≤ **5%** of imported goods'
customs value; cancel status ≥ **5 working days** before the year); tourist-zone hotels until **1 Jan 2026** (expired);
agriculture ≤ GEL 200 000 before 2018 (historic). Art. 99, 24¹.

NEEDS ACCOUNTANT (part 99): the Finance Minister's interest-rate ceiling (98²(1)(ე)), the Government's low-tax country
list (98²(10)), international-company and special-trading-company procedures, the 309(134) procedure, which amendment
introduced each Art. 99 date, and how the expired tourist-zone exemption is handled now.

App candidates: the distribution rule already exists; next would be the representation-expense limit (1%) and the
non-business-expense / free-supply objects, both computable from the books once expenses are categorised.
