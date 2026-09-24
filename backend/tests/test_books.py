"""Sales and expenses: bank statement import, monthly figures, limits, and the chat using recorded sales."""

import base64
import io
import zipfile
from datetime import date
from decimal import Decimal

import pytest

from app.books.importer import find_table, parse_date, parse_money, parse_table, read_rows

GEORGIAN_CSV = """ამონაწერი ანგარიშიდან GE00TB0000000000000000
თარიღი;დანიშნულება;პარტნიორი;დებეტი;კრედიტი
03.09.2026;მომსახურების საფასური;შპს კლიენტი;;11 800,00
05.09.2026;იჯარა;შპს მეიჯარე;1 180,00;
05.09.2026;იჯარა;შპს მეიჯარე;1 180,00;
10.09.2026;;;;
""".encode("utf-8")

SIGNED_CSV = b"""Date,Amount,Description,Counterparty
2026-08-01,"2,500.00",Invoice 17,Client LLC
2026-08-02,-300.5,Office supplies,Shop
2026-08-03,0,Fee reversal,Bank
bad date,100,?,?
"""


def xlsx(rows: list[list[str]]) -> bytes:
    """A minimal real .xlsx: shared strings for text, numbers inline."""
    strings: list[str] = []
    sheet_rows = []
    for r, row in enumerate(rows, start=1):
        cells = []
        for c, value in enumerate(row):
            ref = f"{chr(65 + c)}{r}"
            if isinstance(value, (int, float)):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                strings.append(value)
                cells.append(f'<c r="{ref}" t="s"><v>{len(strings) - 1}</v></c>')
        sheet_rows.append(f'<row r="{r}">{"".join(cells)}</row>')
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("xl/workbook.xml", f'<workbook {ns} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                                      '<sheets><sheet name="S" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                                 '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/sharedStrings.xml", f'<sst {ns}>' + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet {ns}><sheetData>{"".join(sheet_rows)}</sheetData></worksheet>')
    return buffer.getvalue()


@pytest.mark.parametrize("text, value", [
    ("11 800,00", "11800.00"), ("1,234.56", "1234.56"), ("1.234,56", "1234.56"), ("-300.5", "-300.5"),
    ("(250.00)", "-250.00"), ("1,234", "1234"), ("2500,5", "2500.5"), ("1 234 567", "1234567"), ("GEL 99.90", "99.90"),
    ("", None), ("n/a", None),
])
def test_parse_money(text, value):
    assert parse_money(text) == (Decimal(value) if value else None)


@pytest.mark.parametrize("text, value", [
    ("03.09.2026", date(2026, 9, 3)), ("2026-09-03", date(2026, 9, 3)), ("03/09/2026", date(2026, 9, 3)),
    ("2026-09-03T10:22:00", date(2026, 9, 3)), ("46268", date(2026, 9, 3)), ("soon", None),
])
def test_parse_date(text, value):
    assert parse_date(text) == value


def test_georgian_statement_with_debit_and_credit_columns():
    table = find_table(read_rows("statement.csv", GEORGIAN_CSV))
    assert table.header_row == 1
    assert table.mapping == {"date": 0, "description": 1, "counterparty": 2, "expense": 3, "income": 4, "amount": None}
    rows, skipped = parse_table(table)
    assert [(r.occurred_on, r.direction.value, r.amount) for r in rows] == [
        (date(2026, 9, 3), "income", Decimal("11800.00")),
        (date(2026, 9, 5), "expense", Decimal("1180.00")),
        (date(2026, 9, 5), "expense", Decimal("1180.00")),
    ]
    # Two identical rent payments are two payments, with different fingerprints.
    assert rows[1].external_id != rows[2].external_id
    assert [s.reason for s in skipped] == ["no_amount"]


def test_signed_amount_statement():
    rows, skipped = parse_table(find_table(read_rows("x.csv", SIGNED_CSV)))
    assert [(r.direction.value, r.amount, r.counterparty) for r in rows] == [
        ("income", Decimal("2500.00"), "Client LLC"), ("expense", Decimal("300.50"), "Shop")]
    assert sorted(s.reason for s in skipped) == ["no_date", "zero"]


def test_xlsx_statement_with_excel_dates():
    content = xlsx([["Bank statement"], ["Date", "Details", "Money in", "Money out"],
                    [46268, "Sale", 5000, ""], [46269, "Supplier", "", 1200.5]])
    rows, _ = parse_table(find_table(read_rows("statement.xlsx", content)))
    assert [(r.occurred_on, r.direction.value, r.amount) for r in rows] == [
        (date(2026, 9, 3), "income", Decimal("5000.00")), (date(2026, 9, 4), "expense", Decimal("1200.50"))]


def test_file_without_a_header_is_rejected(client):
    company = client.post("/companies", json={"name": "X", "tax_id": "404000001", "legal_form": "LLC",
                                              "registration_date": "2024-01-01"}).json()
    body = {"filename": "x.csv", "content": base64.b64encode(b"just,some\ntext,here").decode()}
    response = client.post(f"/companies/{company['id']}/books/import/preview", json=body)
    assert response.status_code == 422 and response.json()["detail"] == "import.error.no_header"


# ---------- API ----------

def make_company(client, vat_registered=False, legal_form="LLC", regime="standard", tax_id="404123123"):
    company = client.post("/companies", json={"name": "Books Co", "tax_id": tax_id, "legal_form": legal_form,
                                              "registration_date": "2024-01-01"}).json()
    client.put(f"/companies/{company['id']}/tax-profile", json={"vat_registered": vat_registered, "tax_regime": regime})
    return company


def add(client, company, day, direction, amount, **extra):
    response = client.post(f"/companies/{company['id']}/transactions", json={
        "occurred_on": day, "direction": direction, "amount": amount, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_import_preview_then_import_is_idempotent(client):
    company = make_company(client, vat_registered=True)
    body = {"filename": "statement.csv", "content": base64.b64encode(GEORGIAN_CSV).decode()}
    preview = client.post(f"/companies/{company['id']}/books/import/preview", json=body).json()
    assert (preview["total"], preview["income"], preview["expense"], preview["duplicates"]) == (3, 1, 2, 0)
    assert preview["header"][1] == "დანიშნულება"

    first = client.post(f"/companies/{company['id']}/books/import", json={**body, "sales_include_vat": True,
                                                                         "purchases_include_vat": True}).json()
    assert (first["imported"], first["duplicates"]) == (3, 0)
    again = client.post(f"/companies/{company['id']}/books/import", json=body).json()
    assert (again["imported"], again["duplicates"]) == (0, 3)

    records = client.get(f"/companies/{company['id']}/transactions").json()
    sale = next(r for r in records if r["direction"] == "income")
    assert (sale["amount"], sale["vat_amount"], sale["counterparty"]) == ("11800.00", "1800.00", "შპს კლიენტი")


def test_corrected_mapping_is_used(client):
    company = make_company(client)
    # Swap the in/out columns, as a user would if the bank labelled them the other way round.
    body = {"filename": "s.csv", "content": base64.b64encode(GEORGIAN_CSV).decode(),
            "mapping": {"date": 0, "description": 1, "counterparty": 2, "expense": 4, "income": 3, "amount": None}}
    preview = client.post(f"/companies/{company['id']}/books/import/preview", json=body).json()
    assert (preview["income"], preview["expense"]) == (2, 1)


def test_vat_included_is_computed_by_the_rule_and_delete(client):
    company = make_company(client, vat_registered=True)
    t = add(client, company, "2026-09-10", "expense", "590.00", vat_included=True, description="Paper")
    assert t["vat_amount"] == "90.00"
    unregistered = make_company(client, tax_id="404123124")
    assert add(client, unregistered, "2026-09-10", "expense", "590.00", vat_included=True)["vat_amount"] is None
    assert client.delete(f"/companies/{company['id']}/transactions/{t['id']}").status_code == 204
    assert client.get(f"/companies/{company['id']}/transactions").json() == []
    assert client.delete(f"/companies/{company['id']}/transactions/{t['id']}").status_code == 404


def test_month_filter(client):
    company = make_company(client)
    add(client, company, "2026-08-31", "income", "1")
    add(client, company, "2026-09-01", "income", "2")
    got = client.get(f"/companies/{company['id']}/transactions", params={"start": "2026-09-01", "end": "2026-09-30"})
    assert [r["amount"] for r in got.json()] == ["2.00"]


def test_vat_payer_month_summary(client):
    company = make_company(client, vat_registered=True)
    add(client, company, "2026-09-03", "income", "11800", vat_amount="1800")
    add(client, company, "2026-09-05", "expense", "5900", vat_amount="900")
    add(client, company, "2026-08-20", "income", "1000")
    s = client.get(f"/companies/{company['id']}/books", params={"month": "2026-09"}).json()
    assert s["totals"] == {"income": "11800.00", "expense": "5900.00", "output_vat": "1800.00", "input_vat": "900.00",
                           "count": 2}
    assert s["vat_payable"]["amount"] == "900.00" and s["vat_registration"] is None
    assert s["turnover_12m"]["alert"] == "none"  # already registered


@pytest.mark.parametrize("sales, alert, applies", [("50000", "none", False), ("85000", "approaching", False),
                                                    ("100001", "exceeded", True)])
def test_vat_threshold_alert(client, sales, alert, applies):
    company = make_company(client)
    add(client, company, "2025-11-15", "income", sales)
    add(client, company, "2024-06-01", "income", "90000")  # outside the 12 months
    s = client.get(f"/companies/{company['id']}/books", params={"month": "2026-09"}).json()
    assert s["turnover_12m"]["amount"] == f"{Decimal(sales):.2f}"
    assert (s["turnover_12m"]["start"], s["turnover_12m"]["end"]) == ("2025-10-01", "2026-09-30")
    assert s["turnover_12m"]["limit"] == "100000"
    assert s["turnover_12m"]["alert"] == alert
    assert (s["vat_registration"]["status"] == "applies") is applies


def test_small_business_month_and_year(client):
    company = make_company(client, legal_form="IE", regime="small_business", tax_id="01001000001")
    add(client, company, "2026-03-10", "income", "420000")
    add(client, company, "2026-09-10", "income", "30000")
    s = client.get(f"/companies/{company['id']}/books", params={"month": "2026-09"}).json()
    assert s["year_income"]["amount"] == "450000.00" and s["year_income"]["alert"] == "approaching"
    assert s["small_business_tax"]["amount"] == "300.00"  # 1% of 30 000
    add(client, company, "2026-09-20", "income", "60000")
    s = client.get(f"/companies/{company['id']}/books", params={"month": "2026-09"}).json()
    assert s["year_income"]["alert"] == "exceeded"
    assert s["small_business_tax"]["amount"] == "2700.00"  # 3% of 90 000, the whole month (Art. 90(2))


def test_chat_uses_recorded_turnover(client):
    company = make_company(client)
    add(client, company, "2026-05-10", "income", "120000")
    body = client.post(f"/companies/{company['id']}/chat", json={"message": "Do I need to register for VAT?",
                                                                  "as_of": "2026-09-24"}).json()
    assert body["reply"].startswith("Yes, you need to register for VAT.")
    assert "I used the sales recorded in your books: 120,000.00 GEL" in body["reply"]
    assert body["extraction"]["from_books"] == {"taxable_turnover_12m": "120000.00"}


def test_chat_stated_turnover_beats_the_books(client):
    company = make_company(client)
    add(client, company, "2026-05-10", "income", "120000")
    body = client.post(f"/companies/{company['id']}/chat", json={"message": "our turnover is 50,000",
                                                                  "as_of": "2026-09-24"}).json()
    assert body["reply"].startswith("No, you don't need to register.")
    assert body["extraction"]["from_books"] == {}


def test_chat_small_business_limit_from_books(client):
    company = make_company(client, legal_form="IE", regime="small_business", tax_id="01001000002")
    add(client, company, "2026-02-01", "income", "510000")
    body = client.post(f"/companies/{company['id']}/chat", json={"message": "small business tax on 10000",
                                                                  "as_of": "2026-09-24"}).json()
    assert body["reply"].startswith("On 10,000 GEL of income you pay 300.00 GEL")
    assert "Your books show 510,000.00 GEL of income this year so far" in body["reply"]
