"""Check ChatGPT's knowledge-base files against the law text, so only problems need a human (or Claude) to look.

    python -m tools.kb_check                          # moves topic-*-part-*.md from Downloads to Desktop\\Tax knowledge base, checks all
    python -m tools.kb_check topic-04-part-01.md      # or given files / folders only

For every rule (a "RULE:" block, or an "Article …" heading in a compact table) it checks:
- each Georgian quote line appears word for word in the current Tax Code, Customs Code or Law on Funded Pension
  (the rad_law corpus, whitespace and Matsne's split superscripts ignored);
- each number in the rule's CONDITIONS / CALCULATION / DEADLINE (amounts, percentages, dates) also appears in its
  Georgian quote — a number with no quote behind it is flagged, because that is where a misread would hide.
Prints a summary and only the problems. Exit code 1 if anything failed.
"""

import argparse
import json
import re
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

CORPUS = Path(r"C:\Users\iakob\Desktop\rag law\RAD law\data")
KB_FOLDER = Path.home() / "Desktop" / "Tax knowledge base"
DOWNLOADS = Path.home() / "Downloads"
LAWS = {"1043717": "Tax Code", "4598501": "Customs Code", "4280127": "Law on Funded Pension"}
GEORGIAN = re.compile(r"[ა-ჰ]")
SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:[ ,.\u00a0]\d{3})+|\d+(?:[.,]\d+)?)\s*(%|percent|ლარ|GEL)?", re.I)
CHECKED_FIELDS = ("CONDITIONS", "CALCULATION", "DEADLINE")


def normalize(text: str) -> str:
    """Whitespace, quotes and Matsne's split superscripts ('ბ 1 )' for 'ბ¹)') made uniform."""
    text = text.replace("\u00a0", " ").replace("\u200b", "").replace("“", "„").replace("”", "“")
    # Paragraph/subparagraph superscripts ("5¹.", "ბ¹)") are dropped on both sides: Matsne writes them as "5 1 .".
    text = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return re.sub(r"(?<=[\dა-ჰ]) \d{1,2} (?=[).])|(?<=[ა-ჰ]) \d{1,2} ?(?=[„“\"])", "", text).strip()


def current_laws() -> str:
    """The current consolidated texts (Georgian): pages without '?publication=' in their Matsne URL."""
    texts = []
    for raw in (CORPUS / "raw").glob("ka_document_view_*.json"):
        meta = json.loads(raw.read_text(encoding="utf-8"))
        doc_id = re.search(r"/view/(\d+)", meta["url"])
        if doc_id and doc_id.group(1) in LAWS and "publication=" not in meta["url"]:
            texts.append((CORPUS / "processed" / (raw.stem + ".txt")).read_text(encoding="utf-8"))
    if len(texts) < len(LAWS):
        sys.exit(f"Found {len(texts)} of {len(LAWS)} laws under {CORPUS}; is the rad_law corpus downloaded?")
    return normalize(" ".join(texts))


@dataclass
class Rule:
    name: str
    source: str
    quotes: list[str] = field(default_factory=list)
    fields: dict[str, str] = field(default_factory=dict)


def parse(text: str, source: str) -> list[Rule]:
    """Split a file into rules: full blocks start at 'RULE:', compact-table quotes at an 'Article …' heading."""
    rules: list[Rule] = []
    current: Rule | None = None
    field_name: str | None = None
    for line in text.splitlines():
        stripped = line.strip().strip("*#>` ").strip()
        block = re.match(r"(?:\d+\.\s*)?RULE:\s*(\S+)", stripped)
        heading = re.match(r"(Article|Art\.|მუხლი)\s+\d", stripped) and not GEORGIAN.search(stripped[:3]) and len(stripped) < 80
        if block or (heading and not stripped.startswith(("Article 1 ", "Article 2 ")) and ":" not in stripped[-2:]):
            current = Rule(block.group(1) if block else stripped, source)
            rules.append(current)
            field_name = None
            continue
        label = re.match(r"([A-Z][A-Z /]+(?:\([a-z]+\))?):\s*(.*)", stripped)
        if label:
            field_name = label.group(1).strip()
            if field_name.startswith("QUOTE (ka)") and GEORGIAN.search(label.group(2)):
                current and current.quotes.append(label.group(2).strip("\"„“”"))
            elif current is not None:
                current.fields[field_name] = label.group(2)
            continue
        if current is None or not stripped:
            continue
        georgian_share = len(GEORGIAN.findall(stripped)) / max(1, len(re.findall(r"\w", stripped)))
        if georgian_share > 0.6 and len(stripped) >= 12 and "\t" not in line and "|" not in stripped:
            current.quotes.append(stripped.strip("\"„“”"))
        elif field_name in CHECKED_FIELDS:
            current.fields[field_name] = current.fields.get(field_name, "") + " " + stripped
    return [r for r in rules if r.quotes or r.fields]


REFERENCE = re.compile(  # "Art. 154(3)", "Articles 147–152", "Law No. 4022", "Article 309(115)(a)" are not amounts
    r"\b(?:Art(?:icle)?s?\.?|Law(?: of Georgia)? No\.?|No\.|№|paragraphs?|items?)\s*"
    r"[\d⁰¹²³⁴⁵⁶⁷⁸⁹]+(?:\([^)]*\))*(?:\s*(?:[–-]|and|or|,)\s*[\d⁰¹²³⁴⁵⁶⁷⁸⁹]+(?:\([^)]*\))*)*", re.I)


def numbers(text: str, everything: bool = False) -> set[str]:
    """Amounts, percentages and dates in `text`; unless everything=True, small bare numbers (list positions) are skipped."""
    text = REFERENCE.sub(" ", text)
    found = set()
    for m in NUMBER.finditer(text):
        digits = re.sub(r"[ ,.\u00a0](?=\d{3}\b)", "", m.group(1)).replace(",", ".")
        if everything or digits not in {"0", "1", "2", "3", "4"} or m.group(2):
            found.add(digits.rstrip("0").rstrip(".") if "." in digits else digits)
    return found


def check(rule: Rule, law: str) -> list[str]:
    problems = []
    quoted_text = ""
    for quote in rule.quotes:
        q = normalize(quote.rstrip("…").strip())
        if "…" in quote or "..." in quote:
            problems.append(f"quote cut with '…': «{quote[:70]}»")
            continue
        if q in law:
            quoted_text += " " + q
            continue
        lo, hi = 0, len(q)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            lo, hi = (mid, hi) if q[:mid] in law else (lo, mid - 1)
        at = law.find(q[:lo]) + lo if lo else -1
        problems.append(f"quote not in the law after {lo}/{len(q)} chars: quote «{q[lo:lo + 50]}» | law «{law[at:at + 50] if lo else '—'}»")
    in_quotes = numbers(quoted_text, everything=True)
    for name in CHECKED_FIELDS:
        missing = sorted(n for n in numbers(rule.fields.get(name, "")) if n not in in_quotes)
        if missing and rule.quotes:
            problems.append(f"{name} numbers not found in its quote: {', '.join(missing)}")
    if not rule.quotes and any(numbers(rule.fields.get(n, "")) for n in CHECKED_FIELDS):
        problems.append("has amounts/dates but no Georgian quote")
    return problems


QUOTED_FACT = re.compile(  # "100 000 ლარი", "5 პროცენტი", "3 თვე" (years like "2007 წლის" and commodity codes aren't facts)
    r"(?<!\d)(?<!\d )(?!(?:19|20)\d\d\b)(?:\d{1,3}(?: \d{3})+|\d+(?:[.,]\d+)?)(?= ?(?:პროცენტ|ლარ|სამუშაო დღ|კალენდარული დღ|დღ|თვ|წლ|წელ))")


def unstated(rule: Rule, law_quotes: str) -> list[str]:
    """Amounts, percentages and time limits its quote states but the rule's fields never mention: a rule summarising
    a whole article instead of stating each fact."""
    stated = numbers(" ".join(rule.fields.values()), everything=True)
    found = {re.sub(r" (?=\d{3})", "", m.group()).replace(",", ".") for m in QUOTED_FACT.finditer(law_quotes)}
    return sorted(found - stated, key=lambda n: float(n))


def collect_downloads() -> None:
    """Move ChatGPT's topic-NN-part-MM files from Downloads into the knowledge-base folder (newer copies win).
    Also takes them out of topic-*.zip files and topic-* folders (ChatGPT sometimes zips a whole topic)."""
    KB_FOLDER.mkdir(parents=True, exist_ok=True)
    for archive in DOWNLOADS.glob("topic-*.zip"):
        with zipfile.ZipFile(archive) as z:
            for member in z.namelist():
                name = Path(member).name
                if re.match(r"topic-\d+-part-\d+\.(md|txt)$", name, re.I):
                    (KB_FOLDER / name).write_bytes(z.read(member))
                    print(f"unzipped {name} from {archive.name}")
        archive.unlink()
    found = [*DOWNLOADS.glob("topic-*-part-*.*"),
             *(f for d in DOWNLOADS.glob("topic-*") if d.is_dir() for f in d.rglob("topic-*-part-*.*"))]
    for f in sorted(found, key=lambda p: p.stat().st_mtime):
        if f.suffix.lower() not in (".md", ".txt"):
            continue
        name = re.sub(r"\s*\(\d+\)(?=\.\w+$)", "", f.name)  # "topic-02-part-10 (1).md" -> a re-download of the same file
        target = KB_FOLDER / name
        target.unlink(missing_ok=True)
        f.replace(target)
        print(f"moved {f.name} -> {target}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check ChatGPT knowledge-base files against the law text.")
    parser.add_argument("paths", nargs="*", type=Path,
                        help=".md/.txt files or folders (default: collect from Downloads into the knowledge-base folder)")
    args = parser.parse_args()
    if not args.paths:
        collect_downloads()
        args.paths = [KB_FOLDER]
    files = sorted(f for p in args.paths for f in ([p] if p.is_file() else [*p.glob("*.md"), *p.glob("*.txt")]))
    if not files:
        sys.exit("No .md or .txt files found.")
    law = current_laws()
    total = failed = quotes = 0
    coarse: list[str] = []
    rules = [rule for f in files for rule in parse(f.read_text(encoding="utf-8"), f.name)]
    split = {r.name for r in rules if any(other.name.startswith(r.name + ".") for other in rules)}
    for f in files:
        for rule in (r for r in rules if r.source == f.name):
            total += 1
            quotes += len(rule.quotes)
            problems = check(rule, law)
            if problems:
                failed += 1
                print(f"\n✗ {rule.name}  ({rule.source})")
                for p in problems:
                    print(f"    - {p}")
            missing = unstated(rule, normalize(" ".join(rule.quotes)))
            if rule.name in split:  # "vat.x" split into "vat.x.<part>" rules: together they must state every fact
                parts = " ".join(v for r in rules if r.name.startswith(rule.name + ".") for v in r.fields.values())
                missing = [n for n in missing if n not in numbers(parts, everything=True)]
            if len(missing) >= 2 or (missing and rule.name in split):
                coarse.append(f"  {rule.name}  ({rule.source}): {', '.join(missing)}")
    if coarse:
        print("\nToo coarse: the quote states these amounts / time limits but the rule doesn't (ask for one RULE each):")
        print("\n".join(coarse))
    print(f"\n{len(files)} file(s), {total} rules, {quotes} Georgian quotes: "
          f"{total - failed} passed, {failed} with problems, {len(coarse)} too coarse.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
