# Topic 8 — Excise (verified 2026-10-02)

ChatGPT files `Desktop\Tax knowledge base\topic-08-part-00…32, 99.md`: 314 rules (Art. 182–194, 309(100), and Law
No. 1477 of 1 April 2026 Art. 2), one per rate-table row; every quote found in the current Tax Code (or Law No. 1477)
by `python -m tools.kb_check`. Harmless flags: 15 and 8 tetri written as GEL 0.15 / 0.08; the 35 million pack quota cited
from its own row; one quote that folds the lead-in "ი) საქართველოს საბაჟო კოდექსის:" into (ი.ა).

**For the accountant:** the alcohol table, row 7, in the current Code reads "2208 90 380 00 00" (one "00" too many);
ChatGPT wrote 2208 90 380 00. Wine (Art. 188¹(2) definition) has no row in the rate table — confirm it is not excisable.

Checker fixes on the way: rate-table rows written "group | code | goods | unit | rate" are checked cell by cell (the
row's own cells adjacent in the law, the group cells once above them); "1 სმ³" is stored as "1 სმ 3"; "190¹ მუხლით" as
"190 1 მუხლით"; ", and" joins article references; Law No. 1477 (document 6826443) is loaded for its transition article —
amending laws are otherwise left out, since they also contain replaced rates.

Rates (Art. 188, 188¹):

| Goods | Rate | Article |
|---|---|---|
| Cigarettes (2402 20) | GEL 2.75 per 20 + **20%** of retail price; local, ≤ 35 million packs/year: GEL 1.3 + **15%** | 188(1), (1¹) |
| Cigars GEL 2.1 each; cigarillos GEL 2.4 per 20 + **30%**; heated tobacco (2404 11) GEL 2.70 per 20 + 20%; raw/hookah/chewing tobacco GEL 30/kg; nicotine liquids GEL 1.2/ml | | 188(1), (1¹) |
| Retail price set by the tax authority by **1 December**, used from 1 January for a year | | 188(1¹) note |
| Petrol and light distillates GEL 500/t; diesel and kerosene GEL 400–440/t; lubricants and oils GEL 800/t; gases GEL 300/t (natural gas GEL 200 per 1 000 m³); biodiesel GEL 150/t | | 188(1) |
| **Cars (8703), from 2 April 2026:** 0–6 years **GEL 1.50/cm³**, older **GEL 4.50/cm³**; left-hand hybrid 0–6 years −60%; right-hand drive ×3; right-hand electric GEL 3 000; left-hand electric exempt; sports car GEL 100; classic car GEL 1.0/cm³; age = year of the customs declaration − year of manufacture | | 188(9)–(18), 194(5)(ლ) |
| Cars already registered, or shipped before 2 April 2026 (road/rail/self-driven: registered before 1 July 2026), keep the old rate | | Law No. 1477 Art. 2 |
| Motorcycles (8711): GEL 0.7–2.4/cm³ by age (under 1 year 1.5, 2–5 years 0.7, over 14 years 2.4) | | 188(1) |
| Beer GEL 0.12 per litre per 1% vol; fermented drinks GEL 5/l (> 5%) or 0.6/l (≤ 5%); intermediate GEL 5/l; spirits GEL 22.5 per litre of pure alcohol (brandy/listed 2208 codes 15, 2207 ethanol 7.5) | | 188¹ |
| International call termination: 15 tetri/min mobile, 8 tetri/min fixed | | 188(3) |

Filing and payment: month is the period; return and payment by the **15th** of the next month; on import with the import
duty (190–191). Car/motorcycle re-exported within **180 days**: 100% refund (189(8)). Excise stamps on alcohol, tobacco
and e-liquids before sale/import; unused stamps returned within **6 months** (192).

Traveller allowances (194(5)): 200 cigarettes / 50 cigars / 250 g tobacco (or a mix ≤ 100%); 1 l of drinks ≥ 22% (or
1 l ethanol ≥ 80%) or 2 l under 22%, plus 16 l beer; from age **18**; once a day by air, once in 30 days otherwise.
By post: the same tobacco limits plus 4 l alcohol.

NEEDS ACCOUNTANT (part 99): wine treatment; classification of each product; mixed traveller consignments; Finance
Minister orders (retail prices, quota, return form, stamps, adapted-car relief), the Oil and Gas Law, Customs Code
Art. 54, 107, 152.

App candidates: **car import calculator** (excise from engine size, age and steering side, plus Topic 9's import duty
and VAT) — the most asked-about excise in Georgia.
