# Topic 9 — Import (verified 2026-10-02)

ChatGPT files `Desktop\Tax knowledge base\topic-09-part-00…46, 99.md`: 451 rules (Tax Code Art. 159(1)(გ), 164¹, 166,
168, 173, 196–199, 309(131)–(132); Customs Code Art. 37–49, 53–54, 63, 65, 107–108, 137–140, 214), one per tariff row;
every quote found in the current Tax Code / Customs Code by `python -m tools.kb_check`. Harmless flags: "before
1 January 2028" written as "through 31 December 2027" (4 rules).

Corrected by hand (quotes from the wrong paragraph, which the checker can't see because the text is in the law):
Customs Code 37(11)(ა)–(გ) (unpaid / higher / lower final price) had 37(4)(ა)–(გ)'s related-party text; 63(5) (third
party may pay) had 63(3)'s text; 49(2) and 49(3) had only their lead-in lines; Tax Code 164¹(7) was read as "export is
outside the import base" — it says export/re-export happens on the export declaration and its amount is the customs value.

Checker fix: Art. 197's tariff tables have no rate column (the rate is in the lead-in "12-პროცენტიანი განაკვეთით"), so a
row written "№ | code | goods | 12%" is checked without the rate cell when the rule also quotes that lead-in.

The rule we had, checked:

| Our rule | Finding |
|---|---|
| Import VAT 18% on customs value + import duty | 18% correct (166). Base until 1 Jan 2028: customs value + **all** Georgian import charges except VAT (excise too, not only duty) (309(131)); from 2028 also foreign taxes, commission, packing, transport and insurance to the first destination (164¹(2)) |
| Import duty 12% / 5% listed goods, 0% otherwise | 12%: 176 tariff rows, 5%: 37 rows (197(1)–(2)); alcohol has specific rates in euro (197(3)). The Code does **not** say "0% otherwise" in words — accountant to confirm |
| Cars GEL 0.05/cm³ + 5% per year | Confirmed (197(6)): GEL 0.05 per cm³ **plus 5% of that duty for each year in operation**. Refund 100% if exported within **180 days** (198(3)) |

Import VAT (Art. 168, 173):

| Fact | Article |
|---|---|
| Paid like import duty: within **5 days** of release (Minister may set up to **45**); Government-listed machinery HS 8401–9033: **45 days** | 168(2)–(3); CC 65 |
| ~45 exemptions: medicines (HS 30), medical devices, infant food, books/newspapers, **passenger cars (8703) and motorcycles (8711)**, electric buses, civil aircraft, investment gold, grant / humanitarian / diplomatic goods, oil & gas operations | 173 |
| Personal and postal imports within the Art. 199 limits VAT-free until 1 Jan 2028 (not from a free industrial zone) | 309(132) |
| Book X customs reliefs and 173(შ) / 199(ს) suspended until **1 Jan 2028** | CC 214(3), TC 310(4) |

Import duty (Art. 196–199, Customs Code):

| Fact | Article |
|---|---|
| Base: customs value (except alcohol and cars); rules in force when the liability arises (declaration registered) | 196, 198(1); CC 47, 53 |
| Temporary import with partial relief: **3%** of the full duty per started month, by the **15th** of the next month, capped at the full duty; ≤ **3 years** per authorisation, ≤ **10 years** in total | 197(4)–(5); CC 139–140 |
| Personal allowances: GEL **500** / 30 kg (food once a day; other goods once in 30 days), by air GEL **3 000**, by post GEL **300**; returning after > 6 months abroad GEL **15 000**; moving permanently: household goods + one car per family | 199(დ.ა)–(დ.ზ), (ო) |
| Travellers: 200 cigarettes / 50 cigars / 250 g tobacco; 1 l ≥ 22% or 2 l < 22%, 4 l wine, 16 l beer; from age 18; once a day by air, once in 30 days otherwise | 199(დ.გ)–(დ.გ¹), notes |
| Electric cars (8703) duty-free; raw tobacco until 2028; returned goods within **3 years** (+1) unchanged | 199(ჟ), (ი); CC 107 |
| Customs value: 6 methods in order (transaction price first); add commissions, packing, assists, royalties, transport and insurance to the border; exclude Georgian taxes and post-border costs shown separately; related = 5% voting shares etc. | CC 37–44 |

NEEDS ACCOUNTANT (part 99): classification of each good; whether unlisted goods are 0%; preferential origin; the
Government and Finance Minister lists/orders (45-day machinery list, temporary-import list, simplified valuation,
medical lists, 173(რ) agro list) — none in the corpus.

App candidates: **car import calculator** — duty (0.05 × cm³ × (1 + 5% × years)) + excise (Topic 8: GEL 1.50 / 4.50
per cm³, steering and fuel adjustments); no import VAT on HS 8703 (173(ზ)); electric cars duty- and excise-free
(left-hand drive). Also import VAT on goods (18% of customs value + duty + excise) and the personal-parcel limits.
