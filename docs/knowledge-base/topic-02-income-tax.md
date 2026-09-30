# Topic 2 — Income tax on individuals (verification in progress)

Checked against the rad_law corpus: current Georgian Tax Code (`ka_document_view_1043717_24c681cabece13ba`), its English
translation, and the Law on Funded Pension (`ka_document_view_4280127_b2d937a87a6eb6d5`, downloaded 29 Sep 2026).
Amendment dates are ChatGPT's; confirm any date before it becomes an `effective_from`.

## Salary rule already in the app — confirmed

| Fact | Source | Checked |
|---|---|---|
| Income tax 20% of taxable income unless the Code says otherwise | Tax Code 81(1) | quote verbatim |
| Employee's funded-pension contribution is exempt from income tax | Tax Code 82(1)(b³) | quote verbatim |
| Employer's and state's pension contributions are not salary income | Tax Code 101(3)(d) | quote verbatim; English read |
| Employer 2% + employee 2% of taxable salary, paid by the income-declaration day | Funded Pension law 3(6)(a)–(b) | English read |
| State adds 2% on the first GEL 24 000 of annual salary, 1% up to GEL 60 000, nothing above | Funded Pension law 3(6)(e)–(f) | English read |
| Self-employed pay 4% of income | Funded Pension law 3(6)(d) | English read |
| Mandatory for employees, except those already 60 (men) / 55 (women) when the law entered into force; 40+ at that time may leave | Funded Pension law 3(2)–(3), (5) | English read |

So `ge.payroll.income_tax` (tax = 20% × (gross − 2% employee pension); employer 2% on top) matches the law.

## Batch 1 (rules 1–10): 12/12 quotes verbatim

| Rule | Fact | Article |
|---|---|---|
| pit.taxpayer_scope | Taxpayers: resident individuals; non-residents with Georgian-source income | 79 |
| pit.resident_tax_base | Resident's taxable income = annual gross income − deductions allowed by the Code | 80(1) |
| pit.nonresident_pe_base | Non-resident with a Georgian permanent establishment: PE-connected Georgian-source income − deductions | 80(2) |
| pit.nonresident_no_pe_base | Other non-resident income taxed at source without deductions (Art. 134), except property sales and some rent (80(4), (6)) | 80(3)–(6) |
| pit.standard_rate | 20% unless the Code provides otherwise; salary accrued but unpaid before 1 Jan 2008: 12% (309(38), checked) | 81(1) |
| pit.income_classification | Gross income = salary + economic-activity income + other income | 100(3), 101–103 |
| pit.gross_income_exclusions | Items not included in gross income (e.g. agricultural cooperative ↔ member supplies until 1 Jan 2028) | 100(4) |
| pit.foreign_source_exemption | A resident's income that isn't Georgian-source is exempt | 82(1)(ფ) |
| pit.source_employment | Employment performed in Georgia is Georgian-source; where the money is received doesn't matter | 104(1)(ა), (2) |
| pit.source_services | When services count as supplied in Georgia (performed here, tied to Georgian property, resident provider abroad unless via a foreign PE, …) | 104(1)(გ) |

Annual income-tax return: by **1 April** of the following year (153(1), checked).

For the app: the common question from freelancers living in Georgia ("is my income from foreign clients taxed
here?") needs residency (topic 1, Art. 34) *and* the service-source rules, not the foreign-source exemption alone.
Under 104(1)(გ.ზ) a Georgian **resident** providing services to a customer in another state earns **Georgian-source**
income (unless supplied through a foreign permanent establishment that confirms it), so 82(1)(ფ) does not exempt it.
That is why such freelancers typically use small business status (topic 6).

## Batch 2 (rules 11–20): facts checked against the English text

The first version quoted only fragments; ChatGPT redid it with full quotes and law numbers: **28/28 quotes verbatim**
(the royalty line differs only in how Matsne splits the superscript "ბ¹"). Facts also checked against the English text.
ChatGPT kept one misstatement in rule 13 — see the correction row.

| Rule | Fact | Article | Checked |
|---|---|---|---|
| pit.source_investment_income | Dividends from a resident company, sale of shares in a resident company, interest and royalties paid by a resident (or tied to a Georgian PE) are Georgian-source | 104(1)(ვ)–(ი) | summary consistent |
| pit.source_property_other | Leasing movable property used in Georgia, Georgian real estate used in business, and **shares in a company whose assets are > 50% Georgian real estate** are Georgian-source | 104(1)(კ)–(მ) | text read |
| pit.nonresident_withholding | Non-resident without a registered Georgian PE, taxed at source without deductions: dividends/interest per 130/131; **royalties 5%**; international telecom/transport **10%**; oil & gas subcontractors **4%**; rent to an individual and salary at the Art. 81 rate; other Georgian-source **10%**; registered in a preferential-tax country: **15%** on interest, royalties, other | 134(1), (1¹) | text read |
| — correction | 134(2): the **taxes paid** by or for a non-resident's Georgian PE count as paid by a resident enterprise (ChatGPT wrote "payments … treated as payments by a resident enterprise") | 134(2) | text read |
| pit.nonresident_recalculation | For 134(1)(გ)–(ე) income, a return by **1 April** of the next year recalculates on gross income − deductions; tax can't exceed what was withheld | 134(3)–(4) | text read |
| pit.treaty_relief | Treaty relief and refunds follow a Minister of Finance order (not in the corpus) | 125 | not re-read |
| pit.income_recognition | Calendar-year reporting by default; cash or accrual method as in the accounts; monthly periods for listed cases | 135–142 | not re-read |
| salary.income_scope | Salary = any pay or benefit from employment, including pensions from a former employer and pay for future work | 101(1) | text read |
| salary.benefit_employee_payment | A benefit's value is reduced by what the employee paid for it | 101(2) | text read |
| salary.low_interest_loan | Employer loan below the Finance Minister's rate: the benefit is the interest at that rate (rate not in the corpus) | 101(2)(ბ) | text read |
| salary.goods_services_benefit | Employer-provided goods/services: market price | 101(2)(გ) | summary consistent |

## Batch 3 (rules 21–30): 11/11 quotes verbatim

| Rule | Fact | Article |
|---|---|---|
| salary.housing_benefit | Employer housing: annual market rent, pro rata for the period | 101(2)(დ) |
| salary.education_assistance | Education paid for the employee or dependants is a benefit (job-related training excluded) | 101(2)(ე) |
| salary.expense_reimbursement | Reimbursed expenses are a benefit (business trips within the Finance Ministry limits and representation costs excluded, 101(3)(ა)–(ბ)) | 101(2)(ვ) |
| salary.debt_forgiveness | Forgiven debt is a benefit, unless enforcing it would cost more than the debt | 101(2)(ზ) |
| salary.life_health_insurance | Employer-paid life/health insurance premiums are a benefit (compulsory insurance excluded, 101(3)(ე)) | 101(2)(თ) |
| salary.voluntary_private_pension | Employer contributions to a voluntary private pension scheme are a benefit (that law is not in the corpus) | 101(2)(თ¹) |
| salary.other_benefit_market_value | Any other benefit: market price under Art. 18 | 101(2)(ი) |
| salary.employer_car_private_use | Private use of the employer's car: fixed **income tax in lari** per month — > 3 500 cm³: **300**; 2 500–3 500 cm³: **200**; < 2 500 cm³: **100**; any hybrid: **60** (English table read) | 101(2¹) |
| salary.employer_car_tax_deadline | Monthly period; the employer pays by the **15th** of the next month | 101(2²) |
| salary.employer_electric_vehicle_exemption | Private use of the employer's electric car: no income tax | 101(2³) |

App candidate: the employer-car tax is a fixed table with a monthly deadline — an easy, fully sourced rule
(engine size or hybrid/electric → amount; deadline on the 15th).

## Batch 4 (rules 31–40): 18/18 quotes verbatim

| Rule | Fact | Article |
|---|---|---|
| salary.business_trip_reimbursement | Business-trip reimbursement within the Finance Ministry norm is not salary (the norm isn't in the corpus) | 101(3)(ა) |
| salary.representation_reimbursement | Reimbursed representation expenses are not salary | 101(3)(ბ) |
| salary.organized_transport | Employer-organised home↔work transport is not salary when public transport is impossible or unreasonably costly/slow | 101(3)(გ) |
| salary.accumulative_pension_exclusion | Employer's and state's funded-pension contributions are not salary (confirmed with the pension law, see top) | 101(3)(დ) |
| salary.mandatory_insurance_exclusion | Employer-paid **compulsory** insurance is not salary | 101(3)(ე) |
| salary.work_required_housing_food | Housing/food needed because of the employer's activity (or avoiding unreasonable cost/time), and not part of contractual pay, is not salary | 101(3)(ვ) |
| salary.benefit_tax_inclusive | Benefit values include excise, VAT and other taxes the employee would pay | 101(4) |
| salary.loan_rate_minister | The low-interest-loan benchmark rate is set by the Finance Minister (not in the corpus) | 101(5) |
| salary.employer_car_recordkeeping | Recording and reporting employer cars used privately: Finance Minister order (not in the corpus) | 101(2⁴) |
| income.economic_activity_scope | Economic-activity income: supplies, asset gains, interest (except an individual's bank-deposit interest), dividends, royalties, leasing/rent, other | 102(1) |

Still missing from the corpus (Finance Ministry orders): business-trip norms, the employer-loan benchmark rate,
employer-car reporting.

## Batch 5 (rules 41–50): 10/10 quotes verbatim

| Rule | Fact | Article |
|---|---|---|
| income.free_supply_market_value | Free supplies count at market price in gross income (not advertising goods with no consumer value of their own) | 102(2) |
| income.nonemployment_nonbusiness_scope | Other income = any income or benefit not from employment or business, except the listed exclusions | 103(1) |
| income.partner_contribution_exclusion | Partners' contributions that increase the company's net assets are not income | 103(1)(ა) |
| income.health_insurance_payment_exclusion | Health-insurance payouts to the insured person are not income | 103(1)(ბ.ა) |
| income.damage_compensation_exclusion | Insurance payouts up to the actual damage are not income | 103(1)(ბ.ბ) |
| income.uninsured_foreign_vehicle_damage_exclusion | Compulsory Insurance Centre payouts for damage by uninsured foreign-registered cars, up to the damage, are not income | 103(1)(ბ¹) |
| income.control_purchase_secret_assistance_exclusion | Control-purchase costs and covert help to criminal investigators are not income | 103(1)(გ) |
| income.self_employed_state_pension_contribution_exclusion | The state's funded-pension contribution for a self-employed person is not income | 103(1)(დ) |
| income.mandatory_insurance_benefit_exclusion | Employer-paid compulsory insurance is not income | 103(1)(ე) |
| income.other_person_property_benefit_valuation | Property or benefits received from someone are valued by the Art. 101(2) rules | 103(2) |

## Batch 6 (rules 51–60): 19/19 quotes verbatim

| Rule | Fact | Article |
|---|---|---|
| pit.exemption.foreign_diplomatic_employment | Non-residents working at foreign embassies (and equivalents) in Georgia: exempt | 82(1)(ა) |
| pit.exemption.grants_state_payments | Grants, state pensions, state compensation, state (academic) scholarships, budget assistance and one-off payments: exempt | 82(1)(ბ) |
| pit.exemption.state_charity_benefit | Charity from a state-founded non-profit: exempt | 82(1)(ბ¹) |
| pit.exemption.charity_medical_benefit | Charity paying for treatment/medical services: exempt | 82(1)(ბ²) |
| pit.exemption.accumulative_pension | Funded-pension contributions, their returns and pensions paid under the pension law: exempt — **except** refunds of mistaken/excess contributions, refunds on leaving the scheme (pension law Art. 22) and assets returned on leaving Georgia for good (Art. 34¹): those are taxed at **20%** (81(1)) | 82(1)(ბ³) + note |
| pit.exemption.voluntary_private_pension | Voluntary private pension: contributions up to **GEL 6 000 a year** exempt; returns exempt unless withdrawn early; programmed withdrawal/annuity at pension age, early retirement or disability exempt; a lump-sum payout taxes the previously exempt contributions at 20% | 82(1)(ბ⁴) |
| pit.exemption.sports_awards | Awards for Olympic, chess olympiad, world/European championship (etc.) wins or places, and government-set sports prizes: exempt | 82(1)(გ) |
| pit.exemption.alimony | Alimony: exempt | 82(1)(დ) |
| pit.exemption.divorce_property | Property received in a divorce: exempt | 82(1)(ე) |
| pit.exemption.property_sale_gain | Gain on selling: a home with its land owned **> 2 years**; a car owned **> 6 months** after its ownership was registered; another asset owned **> 2 years** and not used in business (business use ignored if it ended 2+ years before the sale; just holding shares for dividends isn't business use): exempt. Gain = sale price − purchase price, or − market value when received free | 82(1)(ვ) + note, 82(4)(ბ) |

App candidates: "I'm selling my apartment / my car — do I pay tax?" is a very common question. With the holding
periods above plus the rate on taxable gains (81(3)–(4), next batches) it's a small, fully sourced rule.
