"""Five languages: catalog completeness, locale formatting, detection, and full replies per language."""

import json
import re
import string
from datetime import date
from decimal import Decimal

import pytest

from app.chat.extractor import KeywordExtractor, detect_language, parse_amount
from app.chat.llm import ungrounded_numbers
from app.i18n import LANGUAGES, MESSAGES_DIR, catalog, format_amount, format_date, plural_category, t, tplural
from app.rules.calendar import load_deadlines
from app.rules.loader import load_rules

NB, NNB = " ", " "


def placeholders(value) -> set[str]:
    texts = value if isinstance(value, list) else list(value.values()) if isinstance(value, dict) else [value]
    return {name for text in texts for _, name, _, _ in string.Formatter().parse(text) if name}


# --- catalogs ---

def test_every_language_has_every_key_with_the_same_placeholders():
    reference = catalog("en")
    for lang in LANGUAGES:
        messages = catalog(lang)
        assert set(messages) == set(reference), lang
        for key, value in reference.items():
            assert type(messages[key]) is type(value), (lang, key)
            assert placeholders(messages[key]) == placeholders(value), (lang, key)
            if isinstance(value, list):
                assert len(messages[key]) == len(value), (lang, key)


@pytest.mark.parametrize("lang, forms", [("ru", {"one", "few", "many"}), ("en", {"one", "other"}),
                                         ("de", {"one", "other"}), ("fr", {"one", "other"}), ("ka", {"other"})])
def test_plural_maps_cover_the_language(lang, forms):
    for key, value in catalog(lang).items():
        if isinstance(value, dict):
            assert set(value) == forms, (lang, key)


def test_every_rule_and_deadline_text_is_in_all_five_languages():
    def localized(node):
        if isinstance(node, dict):
            if "en" in node and all(isinstance(v, str) for v in node.values()):
                yield node
            else:
                for v in node.values():
                    yield from localized(v)
        elif isinstance(node, list):
            for v in node:
                yield from localized(v)

    texts = [text for item in [*load_rules(), *load_deadlines()] for text in localized(item.model_dump())]
    assert len(texts) > 40
    assert all(set(text) == set(LANGUAGES) and all(text.values()) for text in texts)


# --- formatting ---

@pytest.mark.parametrize("lang, grouped, decimal", [
    ("en", "1,234,567", "1,960.00"), ("ka", f"1{NB}234{NB}567", f"1{NB}960,00"), ("ru", f"1{NB}234{NB}567", f"1{NB}960,00"),
    ("de", "1.234.567", "1.960,00"), ("fr", f"1{NNB}234{NNB}567", f"1{NNB}960,00"),
])
def test_format_amount(lang, grouped, decimal):
    assert format_amount("1234567", lang) == grouped
    assert format_amount(Decimal("1960.00"), lang) == decimal
    assert format_amount("425.00", lang).replace(",", ".") == "425.00"  # no grouping below 1000


@pytest.mark.parametrize("lang, expected", [
    ("en", "15 October 2026"), ("ka", "15 ოქტომბერი 2026"), ("ru", "15 октября 2026"),
    ("de", "15. Oktober 2026"), ("fr", "15 octobre 2026"),
])
def test_format_date(lang, expected):
    assert format_date(date(2026, 10, 15), lang) == expected


def test_french_first_of_month_and_punctuation():
    assert format_date(date(2027, 4, 1), "fr") == "1er avril 2027"
    assert t("phrase.need", "fr").endswith(f"informations{NNB}:")


@pytest.mark.parametrize("n, category", [(1, "one"), (21, "one"), (2, "few"), (24, "few"), (5, "many"), (11, "many"),
                                         (12, "many"), (111, "many")])
def test_russian_plurals(n, category):
    assert plural_category(n, "ru") == category


def test_plural_text():
    assert tplural("deadline.in_days", 21, "ru") == "через 21 день"
    assert tplural("deadline.overdue", 3, "ru") == "просрочено на 3 дня"
    assert tplural("deadline.in_days", 1, "de") == "in 1 Tag"
    assert tplural("deadline.in_days", 21, "fr") == "dans 21 jours"


# --- understanding ---

@pytest.mark.parametrize("message, preferred, expected", [
    ("ხელფასი 2500", "en", "ka"), ("зарплата 2500", "en", "ru"), ("Gehalt für Müller", "en", "de"),
    ("Combien de TVA ?", "en", "fr"), ("salary 2500", "de", "en"), ("2500", "fr", "fr"), ("2500", "ka", "en"),
    ("Wie viel ist das?", "en", "de"), ("How much is the salary tax?", "fr", "en"),
])
def test_detect_language(message, preferred, expected):
    assert detect_language(message, preferred) == expected


@pytest.mark.parametrize("text, amount", [
    ("2.500 GEL", "2500"), ("1.234.567,89", "1234567.89"), ("2 500,50 лари", "2500.50"), ("2'500", "2500"),
    (f"8{NNB}500 GEL", "8500"), (f"150{NB}000", "150000"), ("2,50", "2.50"), ("1,5", "1.5"),
])
def test_amounts_in_any_locale(text, amount):
    assert parse_amount(text) == amount


def test_grounding_reads_locale_numbers():
    evidence = '{"net_salary": "1960.00", "income_tax": "490.00", "trace": ["x 0.20"]}'
    assert ungrounded_numbers("Netto 1.960,00 GEL, Einkommensteuer 490,00 GEL (20 %).", evidence) == set()
    assert ungrounded_numbers(f"На руки 1{NB}960,00 лари.", evidence) == set()
    assert ungrounded_numbers("Netto 1.970,00 GEL.", evidence) == {Decimal("1970.00")}


# --- full replies per language ---

@pytest.fixture
def company(client):
    company = client.post("/companies", json={
        "name": "Polyglot LLC", "tax_id": "404121212", "legal_form": "LLC", "registration_date": "2024-01-01"}).json()
    client.put(f"/companies/{company['id']}/tax-profile", json={"vat_registered": True, "has_employees": True})
    return company


def chat(client, company, message, language):
    response = client.post(f"/companies/{company['id']}/chat",
                           json={"message": message, "as_of": "2026-09-24", "language": language})
    assert response.status_code == 200, response.text
    return response.json()


REPLIES = {
    "ru": [
        (f"Я нанял сотрудника с зарплатой 2{NB}500 лари",
         f"При зарплате 2{NB}500 лари до вычетов сотрудник получит на руки 1{NB}960,00 лари."),
        (f"Сколько НДС в 11{NB}800 лари с НДС?",
         f"В сумме 11{NB}800,00 лари с НДС содержится 1{NB}800,00 лари НДС"),
        ("Нужно ли мне регистрироваться плательщиком НДС?",
         "Нет, регистрироваться не нужно. Компания уже зарегистрирована плательщиком НДС"),
        (f"Мы хотим выплатить 8{NB}500 лари дивидендов",
         f"Если компания выплатит 8{NB}500 лари дивидендов, налог на прибыль составит 1{NB}500,00 лари"),
        ("Какие у меня сроки?", "Ближайшие сроки:\n- Декларация и уплата НДС за август 2026: до 15 сентября 2026"),
        ("Здравствуйте", "Здравствуйте! Я ваш налоговый помощник."),
    ],
    "de": [
        ("Ich habe jemanden für 2.500 GEL eingestellt",
         "Bei einem Bruttogehalt von 2.500 GEL erhält der Mitarbeiter 1.960,00 GEL netto."),
        ("Wie viel MwSt. steckt in 11.800 GEL inkl. MwSt.?",
         "11.800,00 GEL inklusive Mehrwertsteuer enthalten 1.800,00 GEL Mehrwertsteuer"),
        ("Muss ich mich für die Mehrwertsteuer registrieren?",
         "Nein, Sie müssen sich nicht registrieren. Das Unternehmen ist bereits für die Mehrwertsteuer registriert"),
        ("Wir möchten 8.500 GEL als Dividende ausschütten",
         "Wenn das Unternehmen 8.500 GEL als Dividende ausschüttet, schuldet es 1.500,00 GEL Gewinnsteuer"),
        ("Welche Fristen habe ich?", "Das steht als Nächstes an:\n- Mehrwertsteuererklärung und Zahlung für August 2026: "
                                     "bis 15. September 2026"),
        ("Guten Tag", "Hallo! Ich bin Ihr Steuerassistent."),
    ],
    "fr": [
        (f"J’ai embauché quelqu’un pour 2{NNB}500 GEL",
         f"Pour un salaire brut de 2{NNB}500 GEL, le salarié touche 1{NNB}960,00 GEL net."),
        (f"Combien de TVA dans 11{NNB}800 GEL TTC ?",
         f"11{NNB}800,00 GEL TTC contiennent 1{NNB}800,00 GEL de TVA"),
        ("Dois-je m’enregistrer à la TVA ?",
         "Non, vous n’avez pas besoin de vous enregistrer. L’entreprise est déjà enregistrée à la TVA"),
        (f"Nous voulons verser 8{NNB}500 GEL de dividendes",
         f"Si l’entreprise verse 8{NNB}500 GEL de dividendes, elle doit 1{NNB}500,00 GEL d’impôt sur les bénéfices"),
        ("Quelles sont mes échéances ?",
         f"Voici les prochaines échéances{NNB}:\n- Déclaration et paiement de la TVA pour août 2026{NNB}: au plus tard "
         "le 15 septembre 2026"),
        ("Bonjour", f"Bonjour{NNB}! Je suis votre assistant fiscal."),
    ],
}


@pytest.mark.parametrize("lang, message, start", [(lang, m, s) for lang, cases in REPLIES.items() for m, s in cases])
def test_reply_in_language(client, company, lang, message, start):
    body = chat(client, company, message, lang)
    assert body["extraction"]["language"] == lang
    first, *rest = start.split("\n")
    assert body["reply"].startswith(first), body["reply"]
    for line in rest:  # list items: present, in whatever order same-day deadlines sort
        assert line in body["reply"], body["reply"]


def test_follow_up_question_and_bare_number_in_german(client, company):
    first = chat(client, company, "Rechnung über 5.000 GEL", "de")
    assert first["reply"] == "Gern. Ist die Mehrwertsteuer in 5.000 GEL bereits enthalten, oder kommt sie noch hinzu?"
    body = {"message": "nein", "as_of": "2026-09-24", "language": "de", "conversation_id": first["conversation_id"]}
    follow_up = client.post(f"/companies/{company['id']}/chat", json=body).json()
    assert follow_up["reply"].startswith("Die Mehrwertsteuer von 18 % auf 5.000,00 GEL beträgt 900,00 GEL")


def test_assumption_and_verification_notes_are_translated(client, company):
    reply = chat(client, company, "Gehalt 2.500", "de")["reply"]
    assert "Ich bin davon ausgegangen, dass der Mitarbeiter am kapitalgedeckten Rentensystem teilnimmt" in reply
    assert "wurde aber noch nicht von einem Steuerberater geprüft" in reply


def test_russian_deadline_plurals(client, company):
    reply = chat(client, company, "Какие у меня сроки?", "ru")["reply"]
    assert "(просрочено на 9 дней)" in reply and "(через 21 день)" in reply


# --- saved language ---

def test_register_and_update_language(make_client):
    client = make_client()
    body = {"email": "lang@example.com", "password": "correct horse battery", "full_name": "L", "language": "de"}
    assert client.post("/auth/register", json=body).json()["language"] == "de"
    assert client.patch("/auth/me", json={"language": "fr"}).json()["language"] == "fr"
    assert client.get("/auth/me").json()["language"] == "fr"
    assert client.patch("/auth/me", json={"language": "es"}).status_code == 422


def test_saved_language_is_the_default_for_latin_messages(client, company):
    client.patch("/auth/me", json={"language": "de"})
    response = client.post(f"/companies/{company['id']}/chat", json={"message": "2500", "as_of": "2026-09-24"})
    assert response.json()["extraction"]["language"] == "de"


def test_catalog_files_are_valid_json_with_no_empty_strings():
    for path in MESSAGES_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        flat = [v for v in data.values() if isinstance(v, str)] + [x for v in data.values() if isinstance(v, list) for x in v]
        assert all(s.strip() for s in flat), path.name
        assert not re.search(r"\{\s*\}", json.dumps(data, ensure_ascii=False)), path.name
