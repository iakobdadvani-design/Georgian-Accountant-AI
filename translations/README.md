# Translation review / თარგმანების შემოწმება

`review.csv` holds every text the app shows, one row each, in English, Georgian, Russian, German and
French. Open it in Excel or Google Sheets (it's UTF-8, so Georgian and Cyrillic display correctly).

**For reviewers:** read your language's column. If a text is wrong, unnatural, or uses the wrong tax
term, write the better version in `<your language> corrected` and, if useful, why in `comment`.
Leave the cell empty when the text is fine.

- Keep everything in `{curly braces}` exactly as it is (the app fills in amounts and dates there).
- `n/a` means your language doesn't use that plural form; leave it.
- `area` says where the text appears: interface, chat replies, tax rules, or deadlines. Tax rule and
  deadline texts matter most: they explain the law to users.

**რეცენზენტისთვის:** წაიკითხეთ თქვენი ენის სვეტი. თუ ტექსტი არასწორია, არაბუნებრივად ჟღერს ან
საგადასახადო ტერმინი არასწორადაა ნათარგმნი, სწორი ვარიანტი ჩაწერეთ სვეტში `ka corrected`, საჭიროების
შემთხვევაში განმარტება კი — `comment`-ში. სწორ ტექსტთან უჯრა ცარიელი დატოვეთ. `{ფიგურულ ფრჩხილებში}`
მოცემული ნაწილები არ შეცვალოთ.

**Applying a reviewed sheet** (from `backend/`):

```powershell
.\.venv\Scripts\python -m tools.translations apply ..\translations\review.csv --dry-run   # check first
.\.venv\Scripts\python -m tools.translations apply ..\translations\review.csv
.\.venv\Scripts\python -m tools.translations export ..\translations\review.csv            # fresh sheet
```

Corrections that change a `{placeholder}` are refused and listed. Run the tests afterwards; a rule text
changed this way needs the accountant's sign-off again (the rule's content changed).
