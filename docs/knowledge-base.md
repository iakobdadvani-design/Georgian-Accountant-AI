# Tax knowledge base: extraction with ChatGPT

Goal: every tax any person or company in Georgia might pay, as rule blocks (rates, thresholds, conditions, dates,
article) that are checked against the law text and then become rule files in `backend/app/rules/data/`, signed off
by an accountant in the app's Rule review screen.

Source files: `C:\Users\iakob\Desktop\Tax documents for ChatGPT` (00 Contents + Parts 01–11, built from the rad_law
Matsne corpus: Tax Code downloaded 19 Sep 2026, Customs Code 29 Sep 2026). Upload them once to a ChatGPT Project.

## Automated routine (from 30 Sep 2026)

ChatGPT writes each batch into a Markdown file instead of the chat; the files go into
`C:\Users\iakob\Desktop\Tax knowledge base`, and a script checks them against the law text:

```powershell
cd backend; .\.venv\Scripts\python -m tools.kb_check   # moves topic-*-part-*.md from Downloads into the folder, then checks
```

It prints only the rules with problems (a Georgian quote not found word for word in the current Tax Code, Customs
Code or Funded Pension law; a quote cut with "…"; a number in CONDITIONS / CALCULATION / DEADLINE that its quote
doesn't contain; a subparagraph quoted under a paragraph's lead-in that isn't in that paragraph), then the rules that are too coarse (the quote states an amount, percentage or time limit the rule
never mentions: one block summarising a whole article), and a summary line. Only those problems need a look; a clean run means the batch is verified.

Add this to the ChatGPT Project instructions:

````
OUTPUT AS FILES
Write every batch into a downloadable Markdown file instead of the chat, using your file/code tool:
- File name: topic-NN-part-MM.md (NN = topic number, MM = batch number, both two digits), e.g. topic-04-part-01.md.
- Contents: only the rule blocks, each starting with a line "RULE: <id>", in the exact OUTPUT FORMAT, with the complete Georgian quote under "QUOTE (ka):" on its own lines (never "…").
- In the chat, reply with just: the download link, the rule ids in the file, and "next: <first rule id of the next batch>".
- The discovery step (article list + rule table) goes into topic-NN-part-00.md the same way.
- The final lists (NEEDS ACCOUNTANT, missing laws/orders, SEE TOPIC n) go into topic-NN-part-99.md.
````

## How each topic goes

1. New chat in the ChatGPT Project; first message: `TOPIC: n — name` (+ the check items for that topic, below).
2. ChatGPT lists the articles and a table of rules; answer `continue` for the full blocks, ~10 at a time.
3. Save its full answer, bring it back to Claude.
4. Claude checks every block against the law text in the corpus (article, numbers, dates, transitional provisions)
   and writes down what's confirmed, corrected or unclear.
5. Confirmed rules become rule files + tests; the accountant signs them off in the app.

## Progress

| # | Topic | ChatGPT done | Checked by Claude | In the app |
|---|---|---|---|---|
| 1 | General rules: taxpayers, residency, definitions, related parties, how deadlines count | ☑ | ☑ [notes](knowledge-base/topic-01-general.md) | ☐ |
| 2 | Income tax on individuals: salary, rent, interest, dividends, property/car sales, gifts, foreign income, exemptions | ☑ | ☑ [notes](knowledge-base/topic-02-income-tax.md) | ☐ |
| 3 | Withholding and tax agents | ☑ | ☑ [notes](knowledge-base/topic-03-withholding.md) | ☐ |
| 4 | VAT | ☑ | ☑ [notes](knowledge-base/topic-04-vat.md) | ☐ |
| 5 | Profit tax (Estonian model) | ☑ | ☑ [notes](knowledge-base/topic-05-profit-tax.md) | ☐ |
| 6 | Special regimes: small/micro business, fixed tax, international companies, free zones, special trading companies | ☑ | ☑ [notes](knowledge-base/topic-06-special-regimes.md) | ☐ |
| 7 | Property tax | ☑ | ☑ [notes](knowledge-base/topic-07-property-tax.md) | ☐ |
| 8 | Excise | ☑ | ☑ [notes](knowledge-base/topic-08-excise.md) | ☐ |
| 9 | Import: customs value, import duty, import VAT (Tax Code + Customs Code) | ☑ | ☑ [notes](knowledge-base/topic-09-import.md) | ☐ |
| 10 | Non-residents and international | ☑ | ☑ [notes](knowledge-base/topic-10-non-residents.md) | ☐ |
| 11 | Administration: registration, returns, audits, disputes, limitation periods | ☐ | ☐ | ☐ |
| 12 | Penalties and sanctions | ☐ | ☐ | ☐ |

Missing laws/orders ChatGPT reports (to download into rad_law): Law on Funded Pension — **downloaded 29 Sep 2026, extra "Part 12" file; upload it to the Project**. Still missing (from topic 1): Labour Code holidays, tax treaties, Law on Entrepreneurs, Securities Market Law, Ministry of Finance / Justice orders on delivery and registration, National Bank third-party payment rules.

## Base prompt (ChatGPT Project instructions)

````
I'm building the knowledge base for an AI accountant for Georgia. It must cover every tax any person or company might pay: individuals, individual entrepreneurs, companies, non-residents, importers. The app never lets an AI calculate: every amount comes from a deterministic rules engine, and each rule needs exact rates, thresholds, conditions, dates and the article it comes from. Your job is to extract those rules from the attached laws, one topic per chat, so a qualified accountant can verify them.

THE FILES
- Part 01: current Tax Code of Georgia (Georgian, legally binding). The main source.
- Part 02: current Customs Code (Georgian, legally binding).
- Parts 03–09: older versions and English translations, for reference only. Always quote article numbers from the current Georgian text.
- Parts 10–11: amending laws in date order. Use them for when a rule took effect or changed.
- 00 Contents: the list of all documents.

RULES FOR YOU
1. Only use the attached texts. Never fill gaps from memory or websites. If something isn't in the files, write "NOT IN FILES".
2. Cite every fact: article, paragraph, subparagraph (e.g. "Art. 165(1)") and the file part.
3. Quote the key sentence in Georgian, with an English translation.
4. If a rule is ambiguous, has exceptions you can't resolve, or depends on a decree or order that isn't attached, mark it "NEEDS ACCOUNTANT" with a one-line reason.
5. Check the transitional provisions near the end of the Code (e.g. "until 1 January 2028") for every rule; they often change it.
6. Don't invent examples. If you give one, show the formula from the law.
7. Stay on the topic I give. If you find a rule that belongs to another topic, list it at the end as "SEE TOPIC n" instead of writing it out.

OUTPUT FORMAT (one block per rule)
RULE: short id, e.g. vat.registration_threshold
TITLE: plain English, one line
WHO PAYS / APPLIES TO:
CONDITIONS: each as "fact operator value"
CALCULATION: formula with every rate and constant
DEADLINE: day + month, what is filed or paid
EXCEPTIONS: each with its article
EFFECTIVE FROM / CHANGED: dates, with the amending law number
SOURCE: Art. …, Part …
QUOTE (ka): "…"
QUOTE (en): "…"
STATUS: CLEAR | NEEDS ACCOUNTANT (reason)

HOW TO WORK
When I write "TOPIC: n — name", first list every article in Part 01 (and Part 02 for customs) that belongs to that topic. Then give a short table of the rules you found (id, title, status), and wait for me to say "continue" before writing the full blocks, in batches of about 10. At the end of the topic give:
- everything marked NEEDS ACCOUNTANT;
- decrees, orders and other laws the articles refer to that are missing from the files;
- rules found for other topics ("SEE TOPIC n").
````

## First message for each topic

Topics 1, 7, 8, 10: just the `TOPIC:` line. The others add the rules the app already has, so ChatGPT confirms or
corrects them:

```
TOPIC: 1 — General rules: taxpayers, residency, key definitions, related parties, how deadlines count
```

```
TOPIC: 2 — Income tax on individuals: salary, rent, interest, dividends, selling property or a car, gifts, foreign income, exemptions

Also check this rule we already have. Confirm it, or correct it with the article that proves it:
- Salary: 2% employee pension + 2% employer pension; income tax 20% of (gross − employee pension). (Art. 81(1), 82(1)(b³); the pension law isn't attached, so say what the Tax Code itself says.)
```

```
TOPIC: 3 — Withholding and tax agents: who withholds what, at which rate, when it's paid and reported

Also check these rules we already have. For each, confirm it, or correct it with the article that proves it:
- Salary: income tax 20% of (gross − 2% employee pension), withheld by the employer and transferred when the salary is paid. (Art. 81(1), 82(1)(b³), 154(3))
- Dividend withholding 5% to individuals, none to Georgian companies. (Art. 130(1)–(2))
```

```
TOPIC: 4 — VAT: registration, rates, what's taxed or exempt, input VAT, reverse charge, refunds

Also check these rules we already have. For each, confirm it, or correct it with the article that proves it:
- VAT registration required once taxable supplies over any 12 months exceed GEL 100 000. (Art. 165(1))
- VAT rate 18%; VAT inside a VAT-inclusive price = 18/118. (Art. 166)
- VAT payable = output VAT − deductible input VAT. (Art. 174–176, 181(1))
```

```
TOPIC: 5 — Profit tax: the "Estonian model", distributions, deemed distributions, banks and other special cases

Also check this rule we already have. Confirm it, or correct it with the article that proves it:
- Profit tax on distributed profit: payout ÷ 0.85 × 15%. (Art. 97(1), 97(10), 98(1))

One RULE block per rate, threshold, time limit or deadline (not one per article), each with the sentence that states it.
```

```
TOPIC: 6 — Special regimes: small business, micro business, fixed tax, international companies, free industrial zones, special trading companies

Also check this rule we already have. Confirm it, or correct it with the article that proves it:
- Small business status: 1% of gross income, 3% once the year's income passes GEL 500 000. (Art. 88(1), 90(1)–(2))
```

```
TOPIC: 7 — Property tax: companies, individuals, land, rates, family-income thresholds
```

```
TOPIC: 8 — Excise: goods, rates, cars, fuel, tobacco, alcohol
```

```
TOPIC: 9 — Import: customs value, import duty, import VAT, exemptions (Tax Code + Customs Code)

Also check this rule we already have. Confirm it, or correct it with the article that proves it:
- Import VAT 18% on customs value plus import duty; import duty 12% or 5% for the listed goods, 0% otherwise; cars GEL 0.05 per cm³ plus 5% per year of age. (Art. 159(1)(c), 164¹, 196–197; Customs Code)
```

```
TOPIC: 10 — Non-residents and international: permanent establishment, source income, double tax treaties
```

```
TOPIC: 11 — Administration: registration, returns, audits, tax decisions, disputes, statute of limitations

Also check this rule we already have. Confirm it, or correct it with the article that proves it:
- Deadlines: VAT return 15th of next month; salary withholding return 15th; profit tax return 15th; property tax 1 April and 15 June; small business return 15th; micro business return 31 March. A deadline on a day off moves to the next working day. (Art. 168(1), 154(3)–(4), 153(10), 205(2)–(4), 93(1¹), 93(1), 3)
```

```
TOPIC: 12 — Penalties and sanctions: late payment, late filing, invoices, cash registers, every fine

Also check these rules we already have. For each, confirm it, or correct it with the article that proves it:
- Late payment interest 0.05% per day, capped at 3 years. (Art. 272)
- Late filing fine 5% of the return's tax per started month up to 2 months, 10% after. (Art. 274)
```

## Other open items

- Import tax in the app (import VAT first, then a car import calculator): proposed, waiting for the owner's go-ahead;
  topic 9 feeds it.
- Language flags: redraw the Georgian flag's crosses accurately, or drop flags and keep the language names; owner to decide.
- rad_law search index doesn't include the Customs Code downloaded on 29 Sep 2026; rebuild it when needed.
