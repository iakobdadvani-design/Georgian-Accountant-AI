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
