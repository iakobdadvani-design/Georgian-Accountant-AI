# Topic 7 — Property tax (verified 2026-10-01)

ChatGPT files `Desktop\Tax knowledge base\topic-07-part-00…16, 99.md`: 141 rules (Art. 8(16), 18(3), 200–206); every
Georgian quote found in the current Tax Code by `python -m tools.kb_check`. Corrected by hand: two exemptions whose
Georgian quotes were shifted by one subparagraph (206(1)(დ) roads/power/cable lines got (ე)'s text, (ე) organisation
property got only "ვ)"). Harmless flags: "before 2004" written as "through 31 Dec 2003"; "more than half" as 50%;
effective dates 2020/2024 from the amending laws (not in the corpus).

Checker fixes on the way: Matsne stores Art. 202(7)(ა.ე)–(ა.ვ) one word per line (quotes now also compared without
whitespace); number-only lines of the land-rate tables count as quote; "202(5)–(7)", "205(12) and (14)" are references;
a number in a clause that cites another article may come from that article's quote in the same topic (the 150% cap);
a rule with no usable Georgian quote is reported.

Companies (Art. 201(1)(ა)–(ბ), 202(1)–(4¹), 205(2)–(10¹)):

| Fact | Article |
|---|---|
| Rate ≤ **1%** of the average annual net book value (start and end of the year) of fixed assets, investment property, uninstalled equipment, unfinished construction, leased-out property | 201(1)(ა), 202(1) |
| Buildings' book value raised **×3** (acquired before 2000 or date unknown), **×2** (2000–2003), **×1.5** (2004) — not with audited revaluation (**4 years**) or Government-listed state enterprises | 202(1)–(2) |
| Leasing companies: ≤ **0.6%** of the initial book value for the whole lease | 202(3¹) |
| Audit at market value: surcharge only from the **30th** day after the demand; that value used for **3** years | 202(4¹) |
| Return and payment by **1 April**; advance (= last year's tax) by **15 June**, reducible if notified by **1 June** of a ≥ **50%** drop; land tax by **15 November** | 205(2)–(7) |
| Liquidation: notice and return within **5 working days**; bankruptcy: missing returns within **15 days** | 205(10)–(10¹) |

Individuals (Art. 201(1)(გ), 202(5)–(9), 205(11)–(14), 206(1)(ა)):

| Fact | Article |
|---|---|
| Taxed: real estate, yachts, helicopters, aircraft, **cars (HS 8703)**, property leased from non-residents, business assets | 201(1)(გ) |
| Exempt (except land) if last year's **family income ≤ GEL 40 000** | 206(1)(ა) |
| Family income < **GEL 100 000**: **0.05–0.2%** of market value; ≥ 100 000: **0.8–1%** (municipality sets the rate); rate in force on **31 December**; prorated for part-year ownership | 202(5), (8)–(9) |
| Family income counts salary, all other income; small-business income at **25%**, market-stall sales at **15%**; excludes gifts/inheritance from family, home sale after > **2 years**, fixed-tax and micro-business income | 202(6)–(7) |
| Return by **1 November** (not needed if nothing is due or the tax authority assesses from last year/registry data); payment by **15 November** | 205(12)–(14) |

Land (Art. 203–204): taxpayer as of **1 April**, rates in force on **1 April**; agricultural land per hectare by
municipality — arable/homestead **GEL 56–100**, hayfields **GEL 16–20**, pasture **GEL 5–16** (20-row and 5-row tables),
municipality may set up to **150%**; non-agricultural land **GEL 0.24/m²** × territorial coefficient ≤ **1.5**; land for
natural-resource licences ≤ **GEL 3/ha**.

Exemptions (Art. 206, ~45): roads, power and cable lines; organisations' non-business property; FIZ property; biological
assets; property leased from a Georgian resident; medical, school and state-university property; parks, cemeteries,
reservoirs, airports; occupied-territory and adjacent land; IDP housing; agricultural land ≤ **5 ha** owned on
**1 Mar 2004** (IDPs: **1 Jan 2011**); new / resettlement land **5 years**; high-mountain residents' land and
enterprises (**10 years**); agricultural cooperatives until **1 Jan 2028**; tourist-zone hotels until 1 Jan 2026
(expired). Exemptions don't apply to land or buildings leased out (206(2)–(3)).

NEEDS ACCOUNTANT (part 99): every municipality's actual rates, coefficients and house/garage land limits; Finance
Minister / Government procedures; the Oil and Gas, Occupied Territories, insolvency, FIZ and high-mountain laws.

App candidates: company property tax from the books' fixed assets (1% cap, 1 April / 15 June / 15 November dates —
the calendar already has 1 April and 15 June), and the individual's GEL 40 000 family-income exemption check.
