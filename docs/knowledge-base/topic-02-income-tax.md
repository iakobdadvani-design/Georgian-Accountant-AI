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
