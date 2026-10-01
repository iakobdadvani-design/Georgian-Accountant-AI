# Topic 4 — VAT (verified 2026-10-01)

ChatGPT files `Desktop\Tax knowledge base\topic-04-part-00…04, 99.md`: 37 rules (Art. 156–181¹), all Georgian quotes
found word for word in the current Tax Code by `python -m tools.kb_check`. Two numbers have no quote of their own and are
fine: 18/118 (ChatGPT's derivation from the 18% rate, not law text) and the 15th in `vat.tax_period` (quoted in
`vat.declaration_payment`, Art. 168(1)).

The app's rules, confirmed:

| App rule | Confirmed by |
|---|---|
| `ge.vat.registration_threshold`: register once taxable supplies over the last 12 calendar months exceed **GEL 100 000** (apply within 2 working days); Art. 165(7) lists what's excluded and included | 165(1), 165(7) |
| `ge.vat.output_vat`: rate **18%**; 18/118 of a VAT-inclusive price is arithmetic from it, not a sentence in the Code | 166 |
| `ge.vat.payable`: output VAT minus deductible input VAT and adjustments; refund/offset of an excess under Art. 181 | 174–176, 181 |
| VAT deadline: return and payment by the **15th** of the next month; listed imports (HS 8401–9033) within 45 days; bankruptcy returns within 15 days | 168(1)–(5) |

Also covered (article level): taxable person and operations (158–160), vouchers (160³), reverse charge (161), forced
sales (161¹), margin scheme for second-hand goods — margin ÷ 1.18, no input credit, at least 24 months (161²), place of
supply (162–162¹), tax point (163–163¹), taxable amount and customs base (164–164¹), cancellation (165¹), liable persons
(165²), exemptions with and without credit (168¹–173), input credit, proportional credit, restrictions, corrections
(177–179), tax invoices (180), refunds incl. EU persons (181–181¹).

Thresholds and time limits (part 05, re-asked 2026-10-01 because the first pass summarised whole articles; one quote
had a one-letter copying slip, ფარგლებს → ფარგლების, corrected by hand):

| Fact | Article |
|---|---|
| Small-value gift: ≤ **GEL 50** per individual per calendar year, excl. VAT (not advertising/representation) | 157(ი) |
| Short-term hire: ships ≤ **90 days**, other vehicles ≤ **30 days** | 157(ყ) |
| Investment gold: bars ≥ 995/1000; coins ≥ 900/1000, issued after **1800**, legal tender | 157(წ) |
| Export in a non-resident traveller's luggage: out within **90 days**, price incl. VAT > **GEL 600** | 172(4)(ე) |
| Hotel assets taken back within **2 years**; free hotel stay for the owner ≤ **60 days** a year | 172(4)(ქ), (ღ) |
| Asset withdrawal by an enterprise > **50%** state/municipal; lottery organiser > **50%** state-owned | 172(4)(ბ), (ს) |
| Mixed-use fixed asset: non-creditable share < **20%** last year → full credit, annual cancellation | 177(5)(ა) |
| Non-creditable share < **5%** of turnover → full credit, no apportionment | 177(7) |
| Adjustment spread: buildings **10 years** (1/10 a year), other fixed assets **5 years** (1/5) | 177(6) |
| Input credit not allowed on an invoice **3 years** after the end of its year; a third-year claim extends the limitation period by **1 year** | 178(დ) |
| Grant recipient: document within **3 months** after the month of the purchase | 181(3) |
| Tourist refund: goods out within **3 months**, one receipt > **GEL 200** excl. VAT | 181(6)(ბ) |

NEEDS ACCOUNTANT (part 99): 14 rules that depend on Finance Minister orders (investment gold, asset transfers, vouchers,
reverse-charge procedure, forced sales, margin scheme, place of supply, registration and cancellation procedure,
non-resident providers, invoice form, refund procedure) or the Government's HS 8401–9033 list — none in the corpus.

App candidates: VAT registration "approaching" already exists; next would be the reverse charge on services bought
from non-residents (common for companies paying foreign software/advertising) and the margin scheme for car dealers.
