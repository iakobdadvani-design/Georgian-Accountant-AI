"""Translation review sheet: export every text, apply reviewers' corrections back (on a copy of the app's files)."""

import csv
import json
import shutil

import pytest

from tools import translations


@pytest.fixture
def app_copy(tmp_path, monkeypatch):
    for part in ("static/i18n.json", "i18n/messages", "rules/data", "rules/deadlines.json"):
        source = translations.APP / part
        target = tmp_path / part
        target.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if source.is_dir() else shutil.copy)(source, target)
    monkeypatch.setattr(translations, "APP", tmp_path)
    return tmp_path


def read(sheet):
    with sheet.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write(sheet, rows):
    with sheet.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=translations.COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def test_export_covers_every_area_and_language(app_copy, tmp_path):
    sheet = tmp_path / "review.csv"
    count = translations.export(sheet)
    rows = read(sheet)
    assert count == len(rows) > 400
    assert {r["area"] for r in rows} == {"interface", "chat replies", "tax rules", "deadlines"}
    assert all(r[lang] for r in rows for lang in translations.LANGS)
    by_id = {r["id"]: r for r in rows}
    assert by_id["ui.app.name"]["ka"] == "ქართული AI ბუღალტერი"
    assert by_id["reply.phrase.payroll_with_pension"]["placeholders"].startswith("{gross}")
    assert by_id["ge.vat.registration_threshold.title"]["en"] == "VAT registration threshold"
    # Plural forms: Russian's few/many get their own rows; languages without a form say so.
    assert (by_id["ui.books.count.few"]["ru"], by_id["ui.books.count.few"]["ka"]) == ("{n} записи", translations.NOT_USED)


def test_unchanged_sheet_applies_nothing(app_copy, tmp_path):
    sheet = tmp_path / "review.csv"
    translations.export(sheet)
    assert translations.apply(sheet) == ([], [])


def test_corrections_are_written_back_and_bad_ones_refused(app_copy, tmp_path):
    sheet = tmp_path / "review.csv"
    translations.export(sheet)
    rows = read(sheet)
    fixes = {
        "ui.app.tagline": ("ka", "საგადასახადო დამხმარე საქართველოს ბიზნესისთვის"),
        "reply.phrase.payroll_ask": ("de", "Gern. Wie hoch ist das monatliche Bruttogehalt?"),
        "ge.vat.registration_threshold.title": ("fr", "Seuil d’immatriculation à la TVA"),
        "reply.phrase.vat_ask_inclusive": ("ru", "Конечно. Эта сумма включает НДС?"),  # drops {amount}
        "ui.books.count.few": ("ka", "{n} ჩანაწერი"),  # Georgian has no "few"
    }
    for row in rows:
        if row["id"] in fixes:
            lang, text = fixes[row["id"]]
            row[f"{lang} corrected"] = text
    write(sheet, rows)

    applied, rejected = translations.apply(sheet, dry_run=True)
    assert len(applied) == 3 and len(rejected) == 2
    ui = json.loads((app_copy / "static/i18n.json").read_text(encoding="utf-8"))
    assert ui["ka"]["app.tagline"] != fixes["ui.app.tagline"][1]  # dry run wrote nothing

    applied, rejected = translations.apply(sheet)
    assert any("placeholders must stay" in r for r in rejected)
    assert any("isn't used in ka" in r for r in rejected)
    ui = json.loads((app_copy / "static/i18n.json").read_text(encoding="utf-8"))
    de = json.loads((app_copy / "i18n/messages/de.json").read_text(encoding="utf-8"))
    vat = json.loads((app_copy / "rules/data/ge_vat.json").read_text(encoding="utf-8"))
    assert ui["ka"]["app.tagline"] == "საგადასახადო დამხმარე საქართველოს ბიზნესისთვის"
    assert de["phrase.payroll_ask"] == "Gern. Wie hoch ist das monatliche Bruttogehalt?"
    assert vat[0]["title"]["fr"] == "Seuil d’immatriculation à la TVA"
    assert translations.apply(sheet)[0] == []  # applying again changes nothing
