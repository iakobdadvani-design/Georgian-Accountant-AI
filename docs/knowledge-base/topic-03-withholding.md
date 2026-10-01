# Topic 3 — Withholding and tax agents (verified 2026-09-30)

ChatGPT files `Desktop\Tax knowledge base\topic-03-part-00…04, 99.md`: 64 rules, 240 Georgian quotes, checked with
`python -m tools.kb_check` — 62 passed; the other 2 only repeat numbers verified elsewhere (Topic 2 rates; the 15th-day
deadline quoted in `taxagent.monthly_information_authority`). Topic-2 overlaps are listed in part 00 as "covered in topic 2".

New in this topic (the rest is in Topic 2):

| Rule | Fact | Article |
|---|---|---|
| taxpayer.tax_agent_definition | A tax agent performs another taxpayer's obligation and is treated as a taxpayer | 20 |
| special_regime.micro_business_no_withholding | Micro-business individuals don't withhold on services they pay for | 94(3) |
| special_regime.small_business_salary_exemption | Small-business employers: salaries up to **GEL 6 000 a year in total** aren't taxed at source if they registered and got the status this year, or had ≤ **GEL 50 000** income last year | 94(4) |
| taxagent.salary_payer_and_exceptions | The salary payer withholds — except free-zone companies paying residents, and non-resident employers without a Georgian PE cost | 154(1)(ა) |
| taxagent.services_to_nonentrepreneur_individual | Businesses paying an individual (not a registered entrepreneur) for services withhold **20%** — not for VAT payers, notaries, private bailiffs, micro/small business or fixed-tax individuals | 154(1)(დ), 81(1) |
| taxagent.gaming_prize / gaming_account | Lottery/bingo/draw organisers withhold on prizes (lottery ≤ GEL 1 000 exempt); slot-hall and online gambling organisers withhold **5%** on player withdrawals (not foreign citizens' online withdrawals) | 154(1)(ე)–(ე¹), 80(8), 81(3²) |
| taxagent.payee_certificate / information | On request, give the employee a certificate of pay and tax; report recipients to the Revenue Service by the **15th** of the next month | 154(3)(ბ)–(გ) |
| taxagent.monthly_declaration | Monthly payroll / withholding return by the **15th** of the next month | 153(5), 154(4) |
| nonresident_employer.self_assessment | Employees of a foreign employer may declare and pay their own salary tax (Finance Minister procedure) | 154(5) |
| withholding.understatement_penalty | Understated tax: **50%** of the shortfall; **10%** if ≤ 5% of the declared tax; **25%** if 5–20%; **10%** if only the timing changed; > **GEL 100 000** = criminal tax evasion; fines per audit capped at the tax assessed | 275 |
| withholding.information_penalty | Wrong/late monthly information causing an excess refund or credit: fine of **twice** the excess (not if corrected before the refund decision) | 288⁴ |
| withholding.employee_register_penalty | Employee not reported to the employee register: **GEL 200 per employee** | 288⁵ |
| withholding.late_payment_surcharge | 0.05% per day (already in the app); supplier/project exemptions don't cover taxes a person withholds as agent | 272 |

App candidates: the small-business GEL 6 000 salary exemption and the 20% withholding on payments to individuals
for services (very common: a company hiring a freelancer who isn't a registered entrepreneur).
