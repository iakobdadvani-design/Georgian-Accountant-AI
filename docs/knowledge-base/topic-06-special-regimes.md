# Topic 6 — Special regimes (verified 2026-10-01)

ChatGPT files `Desktop\Tax knowledge base\topic-06-part-00…08, 99.md`: 95 rules; every Georgian quote found word for word
in the current Tax Code by `python -m tools.kb_check`. Two numbers have no quote of their own and are fine: the 1% in
`small.taxable_income_scope` (quoted in `small.rate_1_percent`, 90(1)) and GEL 2 000 in `fixed.rate_municipality_variation`
(quoted in `fixed.rate_object_1_to_2000`, 95³(1)(ა)).

The app's rule, checked:

| App rule | Finding |
|---|---|
| `ge.small_business.tax` | Correct. 1% of **taxable income** (Georgian-source income except salary and Government-excluded types, 90(3)); **3%** from the **start of the month** in which the year's gross income passes **GEL 500 000** to year-end (90(2)) — the books summary already counts income through the end of the month, so the whole crossing month is at 3%. Not encoded: the **GEL 700 000** limit for wine-tourism / agritourism. |

Small business (individual entrepreneurs, Art. 88–94):

| Fact | Article |
|---|---|
| Status ends from next 1 January if income > GEL 500 000 (700 000 tourism) in **each of 2** calendar years | 89(2)(ა), 89(3) |
| Own request (before year-end): ends 1st of the next month; prohibited activity or **3** cash-register fines in a year: ends retroactively from 1 January | 89(2)–(4) |
| Return and payment by the **15th** of the next month; no advance payments; losses not carried forward | 93(1¹), 94(1), 91(5) |
| Special accounting journal; consignment notes where required; on VAT registration, record stock and claim its input VAT | 91, 92 |
| Salaries up to **GEL 6 000** a year not taxed at source if registered this year, or last year's income ≤ **GEL 50 000** | 94(4) |

Micro business (individuals without employees, Art. 84–87, 93):

| Fact | Article |
|---|---|
| Income ≤ **GEL 30 000** a year (except Government-listed activities); no income tax | 84(1)–(2), 86 |
| Status ends if stock > **GEL 45 000** or on VAT registration; over the income limit: **15 days** to apply for small business status | 85(2)–(3) |
| Annual return by **1 April**; within **30 working days** after stopping activity | 93(1)–(2) |

Fixed tax (Art. 95¹–95⁶): non-VAT payers in Government-listed activities; per object **GEL 1–2 000** (may differ by
municipality) or **3%** of the activity's income; status from the 1st of the month after it is granted; that income is
not taxed again; cancellation application within **10 working days** of the ground. Payment and filing dates are in a
Finance Minister order (not in the corpus).

International companies (Art. 23): Government-listed activities only, granted by the Government, not in a free
industrial zone; an unlisted activity cancels the status from **1 January** of that year; qualifying Georgian costs
reduce the taxable amount; property other than land exempt (rate 5% / ÷ 0.95 in Topic 5).

Free industrial zones (Art. 25, 99(1)(ნ)): **4%** of income on goods supplied to Georgian-registered persons (market price
if free), **4%** of market price on goods bought from them (except electricity, water, gas), both by the **15th** of the
next month; restrictions on buying/supplying local services; profit tax exempt for permitted activity.

Special trading companies (Art. 24¹): status from the tax authority for a purpose-built company; may re-export and supply
foreign goods in a customs warehouse; may not import (except own fixed assets), buy Georgian goods for resale, serve
Georgian businesses or own a customs warehouse; a buyer deducts at most the customs value (limits and exemption in Topic 5).

NEEDS ACCOUNTANT (part 99): the Government lists (micro/small prohibited activities, excluded income, fixed-tax
activities and rates, international-company activities and costs, FIZ services), the Finance Minister's procedures
(status, journals, returns, fixed-tax payment dates, FIZ reporting) and the Law on Free Industrial Zones — none in the corpus.

App candidates: micro business (no tax, GEL 30 000 limit, 1 April return) and the small-business GEL 700 000 tourism
limit and two-year cancellation warning, all computable from the books.
