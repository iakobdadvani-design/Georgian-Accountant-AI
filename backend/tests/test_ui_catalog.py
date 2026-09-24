"""The web UI's translation catalog: complete in every language, and covering every key the page uses."""

import json
import re
import string
from pathlib import Path

from app.i18n import LANGUAGES

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
CATALOG = json.loads((STATIC / "i18n.json").read_text(encoding="utf-8"))
PAGE = (STATIC / "index.html").read_text(encoding="utf-8")


def placeholders(value) -> set[str]:
    if isinstance(value, dict):
        return set().union(*(placeholders(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(placeholders(v) for v in value)) if value else set()
    return {name for _, name, _, _ in string.Formatter().parse(value) if name}


def test_every_language_has_every_key():
    assert set(CATALOG) == set(LANGUAGES)
    reference = CATALOG["en"]
    for lang in LANGUAGES:
        assert set(CATALOG[lang]) == set(reference), (lang, set(reference) ^ set(CATALOG[lang]))
        for key, value in reference.items():
            assert type(CATALOG[lang][key]) is type(value), (lang, key)
            assert placeholders(CATALOG[lang][key]) == placeholders(value), (lang, key)


def test_every_key_used_by_the_page_exists():
    used = set(re.findall(r'data-i18n(?:-placeholder|-aria|-title)?="([^"]+)"', PAGE))
    used |= set(re.findall(r'\bt\("([a-zA-Z_.]+)"', PAGE))
    used |= set(re.findall(r'\btp\("([a-zA-Z_.]+)"', PAGE))
    used |= set(re.findall(r'\blookup\("([a-zA-Z_.]+)"', PAGE))
    # "legal." + form style prefixes are dynamic families, checked by test_dynamic_key_families_are_complete
    missing = {key for key in used if not key.endswith(".") and key not in CATALOG["en"]}
    assert not missing, missing
    assert len(used) > 80


def test_dynamic_key_families_are_complete():
    for lang in LANGUAGES:
        messages = CATALOG[lang]
        for status in ("applies", "not_applicable", "insufficient_data"):
            assert f"card.{status}" in messages
        for verification in ("demo", "unverified", "verified"):
            assert f"card.{verification}" in messages and f"card.{verification}Tip" in messages
        for source in ("claude", "ollama", "keyword", "template"):
            assert f"source.{source}" in messages
        for form in ("LLC", "JSC", "IE", "Other"):
            assert f"legal.{form}" in messages
        for regime in ("standard", "small_business", "micro_business"):
            assert f"regime.{regime}" in messages


def test_no_hard_coded_english_left_in_the_markup():
    body = PAGE.split("<body>", 1)[1].split("<script>", 1)[0]
    text = re.sub(r"<[^>]+>", " ", body)
    words = re.findall(r"[A-Za-z]{4,}", text)
    assert words == [], words  # all visible text comes from data-i18n


def test_suggestions_are_understood_by_the_backend():
    from app.chat.extractor import KeywordExtractor
    for lang in LANGUAGES:
        for suggestion in CATALOG[lang]["suggestions"]:
            assert KeywordExtractor().extract(suggestion["text"], lang).intent != "unknown", (lang, suggestion)


def test_static_catalog_is_served(client):
    response = client.get("/static/i18n.json")
    assert response.status_code == 200
    assert response.json()["ka"]["nav.newChat"] == "ახალი საუბარი"
