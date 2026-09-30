# Topic 1 — General rules (verified 2026-09-29)

ChatGPT output checked against the rad_law corpus: the current Georgian Tax Code
(`ka_document_view_1043717_24c681cabece13ba`, Matsne, downloaded 19 Sep 2026) and its English translation.

- All 18 Georgian quotes in the full rule blocks appear **verbatim** in the current Code.
- Numbers checked against the text: all correct (see table).
- Amendment dates (e.g. Law №1886 of 26 Dec 2013, published 30 Dec 2013) were not individually re-checked; confirm
  any date before it becomes an `effective_from` in a rule file.
- Its "NEEDS ACCOUNTANT" flags are reasonable: they point at laws and orders not in the corpus (Labour Code holidays,
  tax treaties, Law on Entrepreneurs, Securities Market Law, Ministry of Finance / Justice orders, National Bank rules).

## Verified facts

| Rule | Fact | Article | Checked |
|---|---|---|---|
| deadline.start_and_day_type | Counting starts the day after the action; days are calendar days unless stated | 3(2) | quote verbatim |
| deadline.months_and_years | Month/year periods end on the corresponding day/month | 3(3)–(4) | quote verbatim |
| deadline.cutoff_and_rollover | Action by end of the last business day; by **24:00** if by bank transfer, post or electronically; a deadline on a non-business day moves to the next business day (24:00 for those channels) | 3(5)–(6) | text read |
| deadline.year_definitions | Calendar year 1 Jan–31 Dec (newly registered: from registration); "year" = any 12 continuous months | 3(7)–(8) | quote verbatim |
| deadline.payment_fallback | No payment date in the Code → pay by the return deadline; otherwise within **30 days** of receiving the tax demand | 62(2) | quote verbatim |
| deadline.document_receipt | Electronic document delivered when opened; for the Art. 264(2) notice, on the **30th day** after posting if unopened; public posting counts as delivered on the **20th day**; public posting allowed after 30 days unread (companies), or 2 failed written deliveries + no portal account / 30 days unread (individuals) | 44(4), (9)–(11) | text read |
| obligation.creation_and_payment | Payment date = the day the money is **credited to the budget account**, unless the law says otherwise | 53(6) | quote verbatim |
| limitation.assessment_penalty_audit | Assessment, penalties (other than late-payment interest) and audits: **3 years** from the end of the relevant calendar year; +1 year if a return/claim is filed with under a year left; special 14→4-year periods for exempt transactions 2015–2025 | 4(1)–(7), 309(81²) | quote verbatim; 309(81²) schedule read |
| limitation.refund_and_collection | Refund claims: 3 years from the end of the year the right arose; collection acts suspended during insolvency, disputes, deferral agreements etc. | 4(8)–(10) | quote verbatim |
| residency.ordinary_test | Resident for the whole tax year: **183+ days** in Georgia in any continuous 12 months ending in that year, or abroad in Georgian state service | 34(2) | quote verbatim |
| residency.counted_days | Any part of a day in Georgia counts as a day; absences for treatment, rest, business trips, study count; diplomats, international-organisation staff, transit and treatment/rest in Georgia excluded | 34(3)–(5) | quote verbatim |
| residency.special_routes | High-net-worth route (Securities Market Law + ministerial conditions); Georgian citizen with no residency anywhere, on application; foreigners per ministerial rules | 34(6)–(6²) | quote verbatim |
| related.relationship_tests | Related if: co-founders with **≥ 20%** combined; **≥ 20%** direct/indirect participation; control; subordination; common control; relatives; same partnership | 19(2) | quote verbatim |
| related.control_and_ownership | Control = supervisory board, director, right to appoint them, or holding **20%** of voting shares (no "at least" here); relatives' holdings count as indirect | 19(5)–(6) | quote verbatim |
| entity.enterprise | Legal persons, foreign companies and permanent establishments, partnerships; an individual entrepreneur is **not** an enterprise | 21 | quote verbatim |
| individual.entrepreneur | Working without registration, licence or permit doesn't stop someone being taxed as an entrepreneur | 36(2) | quote verbatim |
| taxpayer.registration_and_id | Register before starting economic activity; ID = personal number for citizens, **9-digit** number for non-citizens; permanent | 66(1), (5)–(7) | quote verbatim; 66(6) read |
| period.first_last_and_status_change | Founded before 1 Dec: first period to 31 Dec; founded in December: to 31 Dec of the **next** year; liquidation: 1 Jan to completion; status change splits the period | 59(2)–(8) | quote verbatim; text read |

## What this means for the app

- **Deadlines:** `rules/workdays.py` already moves a deadline on a day off to the next working day (Art. 3(6)). The
  24:00 cut-off for online filing/payment isn't shown anywhere; the calendar could say "by 24:00 online".
- **Late-payment interest:** Art. 53(6) makes the payment date the day the money reaches the budget account, not the
  day the transfer was sent. The "I've paid" date and `rules/lateness.py` assume the user enters the right day; the
  Pay dialog could say so.
- **New feature candidates:** "How far back can the Revenue Service check?" (3 years, Art. 4) and a residency check
  (183 days, Art. 34) — the residency rule belongs with topic 2 (income tax on individuals).
