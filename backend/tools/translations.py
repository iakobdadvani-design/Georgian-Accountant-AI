"""Translation review sheet: every user-visible text in all five languages, for native speakers to check.

    python -m tools.translations export translations/review.csv
    python -m tools.translations apply translations/review.csv      # writes the corrected columns back
    python -m tools.translations apply translations/review.csv --dry-run

Sources: the UI catalog (static/i18n.json), reply catalogs (i18n/messages/<lang>.json), and every
{"ka", "en", ...} text in the rule and deadline files. Each row points at where its text lives, so `apply` can
write a reviewer's correction back. A correction must keep the same {placeholders}. The CSV is UTF-8 with a
BOM so Excel and Google Sheets open Georgian and Cyrillic correctly.
"""

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
LANGS = ("en", "ka", "ru", "de", "fr")
REVIEWED = ("ka", "ru", "de", "fr")  # English is the source
PLACEHOLDER = re.compile(r"\{(\w+)\}")
PLURAL_FORMS = ("zero", "one", "two", "few", "many", "other")
NOT_USED = "n/a"  # a plural form this language doesn't have (Georgian has only "other"; Russian adds few/many)
COLUMNS = ["id", "area", "en", "ka", "ru", "de", "fr", "placeholders",
           *[f"{lang} corrected" for lang in REVIEWED], "comment"]

Path_ = tuple  # JSON path inside a file: keys and list indices


@dataclass
class Unit:
    """One text in every language: where each language's version lives."""

    id: str
    area: str
    locations: dict[str, tuple[Path, Path_]]  # lang -> (file, path)


def rel(path: Path) -> str:
    return path.relative_to(APP).as_posix()


def get(data, path: Path_):
    for step in path:
        data = data[step]
    return data


def put(data, path: Path_, value) -> None:
    get(data, path[:-1])[path[-1]] = value


def leaves(value, path: Path_ = ()):
    """(path, text) for every string inside a catalog value: plain, plural map, list, or list of dicts."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from leaves(v, (*path, k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from leaves(v, (*path, i))


def is_plural(value) -> bool:
    return isinstance(value, dict) and bool(value) and set(value) <= set(PLURAL_FORMS)


def catalog_units(prefix: str, area: str, entries: dict[str, dict], files: dict[str, Path], base: dict[str, Path_],
                  skip) -> list[Unit]:
    """entries: lang -> {key: value}. Plural maps get one row per form any language uses."""
    units = []
    for key, value in entries["en"].items():
        if skip(key):
            continue
        if is_plural(value):
            forms = [f for f in PLURAL_FORMS if any(f in (entries[l].get(key) or {}) for l in LANGS)]
            subs = [(f,) for f in forms]
        else:
            subs = [sub for sub, _ in leaves(value)]
        for sub in subs:
            units.append(Unit(".".join([prefix, key, *map(str, sub)]), area,
                              {lang: (files[lang], (*base[lang], key, *sub)) for lang in LANGS}))
    return units


def ui_units() -> list[Unit]:
    file = APP / "static/i18n.json"
    catalog = json.loads(file.read_text(encoding="utf-8"))
    # locale codes, number separators and the language names themselves aren't prose
    skip = lambda key: key.startswith(("meta.", "number.", "lang.names"))
    return catalog_units("ui", "interface", catalog, {l: file for l in LANGS}, {l: (l,) for l in LANGS}, skip)


def reply_units() -> list[Unit]:
    files = {lang: APP / f"i18n/messages/{lang}.json" for lang in LANGS}
    entries = {lang: json.loads(files[lang].read_text(encoding="utf-8")) for lang in LANGS}
    return catalog_units("reply", "chat replies", entries, files, {l: () for l in LANGS},
                         lambda key: key == "date.format")


def localized(value, path: Path_ = ()):
    """Paths of every {"en": ..., "ka": ...} map inside a rule or deadline file."""
    if isinstance(value, dict):
        if set(value) >= {"en", "ka"} and all(isinstance(v, str) for v in value.values()):
            yield path
            return
        for k, v in value.items():
            yield from localized(v, (*path, k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from localized(v, (*path, i))


def rule_units() -> list[Unit]:
    files = sorted((APP / "rules/data").glob("*.json")) + [APP / "rules/deadlines.json"]
    units = []
    for file in files:
        data = json.loads(file.read_text(encoding="utf-8"))
        area = "deadlines" if file.name == "deadlines.json" else "tax rules"
        for path in localized(data):
            owner = get(data, path[:1])
            name = owner.get("rule_id") or owner.get("deadline_id") or str(path[0])
            field = ".".join(str(p) for p in path[1:])
            units.append(Unit(f"{name}.{field}", area, {lang: (file, (*path, lang)) for lang in LANGS}))
    return units


def all_units() -> list[Unit]:
    return ui_units() + reply_units() + rule_units()


class Files:
    """Loaded JSON files, written back only if something changed."""

    def __init__(self):
        self.data: dict[Path, object] = {}
        self.changed: set[Path] = set()

    def __getitem__(self, file: Path):
        if file not in self.data:
            self.data[file] = json.loads(file.read_text(encoding="utf-8"))
        return self.data[file]

    def text(self, file: Path, path: Path_) -> str:
        try:
            return get(self[file], path)
        except (KeyError, IndexError, TypeError):
            return NOT_USED

    def save(self) -> None:
        for file in self.changed:
            file.write_text(json.dumps(self.data[file], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def export(out: Path) -> int:
    files = Files()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        count = 0
        for unit in all_units():
            texts = {lang: files.text(*unit.locations[lang]) for lang in LANGS}
            source = next(texts[l] for l in LANGS if texts[l] != NOT_USED)
            holders = " ".join(f"{{{p}}}" for p in dict.fromkeys(PLACEHOLDER.findall(source)))
            writer.writerow([unit.id, unit.area, *[texts[lang] for lang in LANGS], holders, *[""] * len(REVIEWED), ""])
            count += 1
    return count


def apply(sheet: Path, dry_run: bool = False) -> tuple[list[str], list[str]]:
    """Returns (applied, rejected) descriptions."""
    units = {u.id: u for u in all_units()}
    files = Files()
    applied, rejected = [], []
    with sheet.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            unit = units.get(row["id"])
            for lang in REVIEWED:
                fix = (row.get(f"{lang} corrected") or "").strip()
                if not fix:
                    continue
                if unit is None:
                    rejected.append(f"{row['id']}: no such text any more")
                    continue
                file, path = unit.locations[lang]
                if files.text(file, path) == NOT_USED:
                    rejected.append(f"{row['id']} [{lang}]: this plural form isn't used in {lang}")
                    continue
                english = next(files.text(*unit.locations[l]) for l in LANGS if files.text(*unit.locations[l]) != NOT_USED)
                if sorted(PLACEHOLDER.findall(fix)) != sorted(PLACEHOLDER.findall(english)):
                    rejected.append(f"{row['id']} [{lang}]: placeholders must stay {sorted(set(PLACEHOLDER.findall(english)))}")
                    continue
                if files.text(file, path) == fix:
                    continue
                put(files[file], path, fix)
                files.changed.add(file)
                applied.append(f"{row['id']} [{lang}] ({rel(file)})")
    if not dry_run:
        files.save()
    return applied, rejected


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("export").add_argument("csv", type=Path)
    a = sub.add_parser("apply")
    a.add_argument("csv", type=Path)
    a.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if args.command == "export":
        print(f"{export(args.csv)} texts written to {args.csv}")
        return 0
    applied, rejected = apply(args.csv, args.dry_run)
    for line in applied:
        print(("would apply " if args.dry_run else "applied ") + line)
    for line in rejected:
        print("REJECTED " + line)
    print(f"{len(applied)} correction(s){' (dry run)' if args.dry_run else ''}, {len(rejected)} rejected")
    return 1 if rejected else 0


if __name__ == "__main__":
    sys.exit(main())
