# Landing page redesign — brief

Apply this redesign to `backend/app/static/landing.html`. The mockup is
[`landing-redesign.reference.html`](landing-redesign.reference.html) (also on the design canvas:
https://claude.ai/artifact/AbeGzZTfjDbJJsVoHM851V, board "★ Homepage redesign (visual)"). The mockup is a
static design file: copy its look, not its markup (it has hard-coded English and inline styles).

Goal: **more graphic and visual, less text.** Keep the brand (ink `#0e1525`, paper `#f6f4ee`, lime `#d4f36b`,
wine `#8c1d33`, Fraunces + IBM Plex Sans). No email field in the hero.

## Project rules that still apply (from CLAUDE.md)

- Every visible text is an `lp.*` key in `static/i18n.json`, in all 5 languages (ka, en, ru, de, fr). New keys
  in all five; flag the new translations for native review and re-run
  `python -m tools.translations export ../translations/review.csv`.
- No hard-coded English in `<body>` before `<script>` (`test_no_hard_coded_english_on_the_landing_page`).
- Amounts go through `money()` (catalog `number.group` / `number.decimal`), never `Intl`, never typed into a
  translation.
- Demo figures stay illustrative and labelled "Example". Don't invent customers, stats or accountant names.
- Run `.\.venv\Scripts\python -m pytest -q -p no:warnings` before committing.

## Changes, in priority order

1. **Hero shows on first paint.** Today the hero has `.reveal` and the whole page waits for `i18n.json`
   (about 1.2 s blank on load). Remove `.reveal` from everything in the hero and render the text before the
   catalog arrives (e.g. inline the current language's `lp.hero.*` strings, or server-render the default
   language), then swap languages after.
2. **One number format.** `lp.demo.q` / `lp.demo.a` contain hand-typed amounts ("11 800 GEL", "1 800,00 GEL")
   while the card uses `money()` ("1,800.00 ₾"). Change both strings to an `{amount}` placeholder in all 5
   languages and fill it with `money(11800)` / `money(1800)`. Use ₾ everywhere on the site.
3. **Hero graphic** (mockup: right side of the hero). Phone frame with the existing chat demo inside, a large
   lime circle with a faint ₾ behind it, two thin slowly rotating rings (60 s per turn), and three floating
   cards: next deadline (mini month grid with the due day pulsing), "RS.ge" synced chip (`lp.s.rs`), Tax Code
   article chip. Headline: the last word in lime. Drop the three tick lines under the CTAs.
4. **Services as a picture grid (bento)** instead of 12 equal cards. Six big tiles, each a small animated
   graphic + title, linking to the same `/app#…` views:
   - AI accountant (wide, dark): three chat bubbles.
   - Small business 1%: progress ring filling toward the GEL 500 000 limit (example value, labelled).
   - Sales & expenses: four bank rows sliding in with Sale / Expense chips.
   - VAT (lime tile): three growing bars — sales, purchases, to pay.
   - Tax calendar (wide): month grid with the 15th highlighted + a reminder chip.
   - The other services (payroll, dividends, penalties, currency, payments, RS.ge, banks) become a row of
     link chips under the grid.
   Keep `GROUPS`/`APP_VIEW` as the source of links so the mega menu and tests keep working.
5. **How it works: three pictures, few words.** 1 = statement file → ₾ tile, 2 = dark tile with the VAT
   formula `11,800 × 18 ÷ 118 = 1,800.00 ₾` and "§ Art. 166", 3 = lime tile with a "Paid" check card.
   (Formula numbers through `money()`.)
6. **Trust section with people.** Replace the four text points with two accountant cards + one customer
   quote card. Until real people/quotes exist, **hide this block** (don't ship placeholders); keep the
   current "law behind every answer" chip.
7. **Colour discipline.** Service icons/tiles: no rainbow (`--teal/--blue/--violet/--indigo`); ink, paper,
   lime, wine only. Green/amber/red only for status.
8. **Motion.** Reveals: 12 px rise, 450 ms (now 26 px / 800 ms), stagger capped at 4 items, start earlier
   (`rootMargin: "0px 0px 15% 0px"`). Hover: 2 px lift, 150 ms (cards now lift 6 px). Keep
   `cubic-bezier(.2,.7,.2,1)` and the reduced-motion block; add the new looping animations to it.
9. **Pricing.** "Most chosen" → "Recommended" (`lp.plan.popular`, all languages). Bigger prices (72 px).
   Faint ₾ in the dark plan. The "coming soon" plan's button: don't send people to `/app#register` under
   "Tell me when it's ready" — show a disabled "Coming soon" until there is a waitlist.
10. **Mobile menu.** Start free + Sign in at the top; services grouped under their 4 group names instead of
    12 rows; show the logo name on phones.
11. **Small fixes.** `og:image` + `og:title`/`og:description`; `alt` text on bank logos (or `alt=""` with
    the name next to it, as now — fine); footer links ≥ 44 px tap height.
12. **Bank logos.** Consider "Reads statements from TBC, Bank of Georgia…" without logos unless the banks
    have agreed; the logo strip reads as a partnership.

## Done when

- Page looks like the mockup at 1440 px and works at 375 px (no horizontal scroll).
- Hero text visible immediately on a cold load.
- All tests pass; new keys exist in all 5 languages; review sheet regenerated.
