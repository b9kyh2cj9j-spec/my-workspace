"""Build the designed Disney book (HTML) from disney-master-2026.md.

Run: python3 build/build_book.py   (from the disney-2026 folder)
Output: book/disney-book.html
Content rules follow chapter 20 of the master document: only chapters
1-19, 21, 22 go in; nothing is added.
"""
import hashlib
import html
import re
from pathlib import Path

import markdown
from bs4 import BeautifulSoup, NavigableString

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "disney-master-2026.md"
OUT = ROOT / "book" / "disney-book.html"

TOOLBOX = list(range(7, 20))
PARK = {4: "hs", 5: "mk", 6: "ak", 10: "mk", 11: "mk"}

TAGS = {
    "🟢": ("ok", "מאומת"),
    "🔵": ("ok2", "נבדק"),
    "🟡": ("warn", "תלוי מצב"),
    "🟠": ("warn2", "לאמת"),
    "⏳": ("open", "פתוח"),
    "🔴": ("bad", "לא בתוקף"),
    "⛔": ("bad", "לא אצלנו"),
    "⚡": ("dec", "הוכרע"),
    "✂": ("open", "הושמט"),
}

PHRASES = {
    "We're checking in today": ("מלון וצ'ק‑אין", "אנחנו עושים צ'ק‑אין היום. תוכלו להעביר את התיקים לחדר כשהוא יהיה מוכן?"),
    "Is resort package delivery": ("מלון וצ'ק‑אין", "יש משלוח של קניות מהפארק למלון?"),
    "Main lodge building please": ("מלון וצ'ק‑אין", "בבניין הראשי בבקשה, רחוק מצד Boulder Ridge אם אפשר (רעש בנייה). תודה!"),
    "Hi! Would it be possible": ("מושבים", "אפשר לשבת בשורה הראשונה? נשמח לחכות לסבב הבא."),
    "Could we wait for the front row": ("מושבים", "אפשר לחכות לשורה הראשונה? (ספארי)"),
    "Is there any chance we could be in the blue": ("מושבים", "יש סיכוי שנהיה בקבוצה הכחולה או האדומה? (הרכב הקדמי ב‑Rise)"),
    "Could we have a back row": ("מושבים", "אפשר שורה אחורית? אנחנו מנסים להירטב פחות."),
    "Any chance we could get row 9": ("מושבים", "יש סיכוי לשורה 9 או 10? (Cosmic Rewind)"),
    "Could we get B1": ("מושבים", "אפשר B1, בבקשה? (Soarin')"),
    "My daughter is a little nervous": ("מושבים", "הבת שלי קצת חוששת. יש מקום שמרגיש פחות עוצמתי?"),
    "No problem at all": ("מושבים", "בכלל לא בעיה, תודה!"),
    "Do you have any holiday Magic Shots": ("מסיבה וצילום", "יש לכם הלילה Magic Shots של החג?"),
    "Our party night was affected": ("מסיבה וצילום", "ערב המסיבה שלנו נפגע ממזג האוויר. יש משהו שתוכלו להציע?"),
    "Hi — I'm not sure": ("תקלות ו‑Guest Relations", "לא בטוח שזה בתחום שלכם. היה לנו Lightning Lane ל‑Space Mountain בין 2 ל‑3, והמתקן נתקע ב‑2:10. לא רואים כלום באפליקציה. זה היה אמור להתעדכן, או שצריך לעשות משהו?"),
    "Totally understand these things": ("תקלות ו‑Guest Relations", "מבינים לגמרי שדברים כאלה קורים. רק לא היינו בטוחים מה האפשרויות שלנו עכשיו. יש משהו שהייתם ממליצים?"),
    "My daughter was really looking": ("תקלות ו‑Guest Relations", "הבת שלי מאוד חיכתה למתקן הזה. אני מבין לגמרי אם אין מה לעשות, רק חשבתי לשאול."),
    "No worries at all": ("תקלות ו‑Guest Relations", "הכול בסדר, תודה שבדקת."),
}
PHRASE_GROUPS = ["מלון וצ'ק‑אין", "מושבים", "מסיבה וצילום", "תקלות ו‑Guest Relations"]

DAYS = {
    4: dict(id="day1", park="hs", num="6.12", wd="יום א'", label="יום 1", name="Hollywood Studios",
            facts=["EE 8:30 · 9:00–21:00", "Fantasmic 21:30, מקומות שמורים",
                   "LL: Rise SP 13:15 · TSMania 9:00 · Frozen 11:30 · RnRC 12:00", "לא בתוכנית: Tower of Terror"]),
    5: dict(id="day3", park="mk", num="8.12", wd="יום ג'", label="יום 3 · טיוטה", name="Magic Kingdom + המסיבה",
            facts=["EE 8:30 · 9:00–18:00", "המסיבה 19:00–0:00", "מצעד 20:30 · זיקוקים 22:00",
                   "Multi Pass בלבד"], draft=True),
    6: dict(id="day4", park="ak", num="9.12", wd="יום ד'", label="יום 4", name="Animal Kingdom → Magic Kingdom",
            facts=["AK 8:00–18:00 · הגעה 9:00", "Happily Ever After 20:00 ב‑MK",
                   "LL: Everest 9:30 · Lion King 12:00 · Na'vi 16:50"]),
}

DAY_CARDS = [
    ("6.12", "א'", "Hollywood Studios", "hs", "יש תוכנית", "ok", "#day1"),
    ("7.12", "ב'", "לא נקבע", "gen", "פתוח", "open", None),
    ("8.12", "ג'", "Magic Kingdom + המסיבה", "mk", "החלטות, בלי לו\"ז מלא", "warn", "#day3"),
    ("9.12", "ד'", "Animal Kingdom → MK", "ak", "יש תוכנית", "ok", "#day4"),
    ("10.12", "ה'", "לא נקבע", "gen", "פתוח", "open", None),
    ("12/13.12", "", "היום השישי", "gen", "לבדוק: 12.12 שבת", "warn", None),
]

TIME_RE = re.compile(r"^~?\d{1,2}:\d{2}")
RANGE_RE = re.compile(r"\$?\d[\d:.,]*\$?(?:\s?[–\-]\s?\$?\d[\d:.,]*\$?)+")
# English runs (with their digits) or numeric ranges: kept in LTR isolation so RTL text doesn't reorder them
LTR_RE = re.compile(r"[A-Za-z][A-Za-z0-9'’&+:/\-–.,!? ]*[A-Za-z0-9!?']|" + RANGE_RE.pattern)


def split_chapters(md):
    chapters, cur = {}, None
    for line in md.split("\n"):
        m = re.match(r"^## (\d+)\. (.+)$", line)
        if m:
            cur = int(m.group(1))
            title = re.sub(r" \((?:MODE|מהמדריך)[^)]*\)", "", m.group(2)).strip()
            chapters[cur] = {"title": title, "lines": []}
            continue
        if line.startswith("# ") or line.strip() == "---":
            if line.startswith("# "):
                cur = None
            continue
        if cur is not None:
            chapters[cur]["lines"].append(line)
    for c in chapters.values():
        c["md"] = "\n".join(c["lines"]).strip()
    return chapters


def drop_subsection(md, start_heading):
    """Remove an ### subsection (heading through the line before the next ###)."""
    lines, out, skip = md.split("\n"), [], False
    for line in lines:
        if line.startswith("### "):
            skip = line.startswith(start_heading)
        if not skip:
            out.append(line)
    return "\n".join(out)


def render(md):
    return markdown.markdown(md, extensions=["tables", "sane_lists"])


def chip(kind, word):
    return f'<span class="chip c-{kind}">{word}</span>'


def tag_chips(htm):
    for emo, (kind, word) in TAGS.items():
        htm = htm.replace(emo + "️", emo).replace(emo, chip(kind, word))
    htm = htm.replace("✅", chip("ok", "✓"))
    return htm


def is_phrase(text):
    t = text.strip().strip('"')
    return text.strip().startswith('"') and len(t.split()) >= 4 and re.search(r"[A-Za-z]", t) and t[-1:] in "?!."


def transform(soup, chapter_no, phrases):
    # tables scroll in their own box
    for t in soup.find_all("table"):
        wrap = soup.new_tag("div", attrs={"class": "tbl"})
        t.wrap(wrap)
    # English phrases
    for em in soup.find_all("em"):
        if is_phrase(em.get_text()):
            text = em.get_text().strip().strip('"')
            em.name = "q"
            em.attrs = {"class": "phrase", "dir": "ltr", "lang": "en"}
            em.string = text
            phrases.append((chapter_no, text))
    # timelines
    for ul in soup.find_all("ul"):
        lis = ul.find_all("li", recursive=False)
        timed = [li for li in lis if li.contents and getattr(li.contents[0], "name", None) == "strong"
                 and TIME_RE.match(li.contents[0].get_text())]
        if len(lis) >= 4 and len(timed) >= len(lis) * 0.7:
            box = soup.new_tag("div", attrs={"class": "tl"})
            for li in lis:
                row = soup.new_tag("div", attrs={"class": "tl-row"})
                t = soup.new_tag("div", attrs={"class": "tl-time"})
                body = soup.new_tag("div", attrs={"class": "tl-body"})
                first = li.contents[0] if li.contents else None
                if first is not None and getattr(first, "name", None) == "strong" and TIME_RE.match(first.get_text()):
                    first.extract()
                    t.append(first.get_text())
                for c in list(li.contents):
                    body.append(c.extract())
                if "מנוחה" in body.get_text():
                    row["class"] = ["tl-row", "rest"]
                row.append(t)
                row.append(body)
                box.append(row)
            ul.replace_with(box)
    # cut lines: if -> then
    for h in soup.find_all("h3"):
        if "Cut lines" not in h.get_text():
            continue
        ul = h.find_next_sibling()
        if ul is None or ul.name != "ul":
            continue
        box = soup.new_tag("div", attrs={"class": "ifs"})
        for li in ul.find_all("li", recursive=False):
            strong = li.find("strong")
            item = soup.new_tag("div", attrs={"class": "ift"})
            cond = soup.new_tag("div", attrs={"class": "if"})
            then = soup.new_tag("div", attrs={"class": "then"})
            cond.append(BeautifulSoup('<span class="k">אם</span>', "html.parser"))
            then.append(BeautifulSoup('<span class="k">אז</span>', "html.parser"))
            if strong is not None and li.contents and li.contents[0] is strong:
                strong.extract()
                cond.append(strong.get_text().rstrip(":"))
            for c in list(li.contents):
                then.append(c.extract())
            item.append(cond)
            item.append(then)
            box.append(item)
        ul.replace_with(box)
    # 🕵️ record cards
    for p in soup.find_all("p"):
        if not p.get_text().lstrip().startswith("🕵"):
            continue
        card = soup.new_tag("article", attrs={"class": "rec"})
        title = soup.new_tag("h4")
        title.string = p.get_text().replace("🕵️", "").replace("🕵", "").strip()
        nodes = []
        sib = p.next_sibling
        while sib is not None:
            nxt = sib.next_sibling
            if getattr(sib, "name", None) in ("h2", "h3") or (
                    getattr(sib, "name", None) == "p" and sib.get_text().lstrip().startswith("🕵")):
                break
            nodes.append(sib)
            sib = nxt
        p.replace_with(card)
        card.append(title)
        for n in nodes:
            card.append(n.extract())
        for li in card.find_all("li"):
            kids = [k for k in li.contents if not (isinstance(k, NavigableString) and not k.strip())]
            if len(kids) == 1 and getattr(kids[0], "name", None) == "em":
                meta = soup.new_tag("p", attrs={"class": "meta"})
                meta.string = kids[0].get_text()
                li.extract()
                card.append(meta)
    # keep numbers and ranges in LTR order inside Hebrew text
    for node in list(soup.find_all(string=True)):
        if node.parent.name in ("q", "script", "style") or {"tl-time", "n"} & set(node.parent.get("class") or []):
            continue
        s = str(node)
        if not LTR_RE.search(s):
            continue
        parts, last = [], 0
        for m in LTR_RE.finditer(s):
            parts.append(html.escape(s[last:m.start()]))
            parts.append(f'<span class="n" dir="ltr">{html.escape(m.group(0))}</span>')
            last = m.end()
        parts.append(html.escape(s[last:]))
        node.replace_with(BeautifulSoup("".join(parts), "html.parser"))
    for t in soup.select(".tl-time"):
        t["dir"] = "ltr"


def chapter_html(no, ch, phrases, extra_class="", header=None):
    md = ch["md"]
    if no == 1:
        md = drop_subsection(md, "### ימי דיסני")
        md = md.replace("### ההחלטות של עומרי", "<!--DAYCARDS-->\n\n### ההחלטות של עומרי")
    body = tag_chips(render(md))
    soup = BeautifulSoup(body, "html.parser")
    transform(soup, no, phrases)
    inner = str(soup)
    if no == 1:
        inner = inner.replace("<!--DAYCARDS-->", day_cards())
    park = PARK.get(no, "gen")
    head = header if header is not None else (
        f'<header class="ch-head"><span class="ch-no">{no}</span><h2>{ch["title"]}</h2></header>')
    return f'<section class="chapter park-{park} {extra_class}" id="ch{no}">{head}<div class="ch-body">{inner}</div></section>'


def day_cards():
    cards = []
    for date, wd, name, park, status, kind, href in DAY_CARDS:
        tag = "a" if href else "div"
        attr = f' href="{href}"' if href else ""
        cards.append(
            f'<{tag} class="dcard park-{park}"{attr}><span class="dc-date" dir="ltr">{date}</span>'
            f'<span class="dc-wd">{wd}</span><span class="dc-name">{name}</span>{chip(kind, status)}</{tag}>')
    return '<h3>ימי דיסני</h3><div class="dcards">' + "".join(cards) + "</div>"


def day_header(d):
    facts = "".join(f"<li>{ltr_ranges(f)}</li>" for f in d["facts"])
    draft = '<p class="draft">טיוטה: החלטות ושלד בלבד. עדיין אין לו"ז מלא.</p>' if d.get("draft") else ""
    return (f'<header class="day-head"><div class="dh-top"><span class="dh-label">{d["label"]}</span>'
            f'<span class="dh-wd">{d["wd"]}</span></div><div class="dh-date" dir="ltr">{d["num"]}</div>'
            f'<h2>{d["name"]}</h2><ul class="facts">{facts}</ul>{draft}</header>')


def ltr_ranges(text):
    out, last = [], 0
    for m in LTR_RE.finditer(text):
        out.append(text[last:m.start()])
        out.append(f'<span class="n" dir="ltr">{m.group(0)}</span>')
        last = m.end()
    out.append(text[last:])
    return "".join(out)


def phrasebook(phrases):
    seen, groups = set(), {g: [] for g in PHRASE_GROUPS}
    for _, text in phrases:
        if text in seen:
            continue
        seen.add(text)
        key = next((k for k in PHRASES if text.startswith(k)), None)
        if key is None:
            raise SystemExit(f"No translation for phrase: {text}")
        group, he = PHRASES[key]
        groups[group].append((text, he))
    out = []
    for g in PHRASE_GROUPS:
        items = "".join(
            f'<li class="pcard"><q class="phrase" dir="ltr" lang="en">{html.escape(en)}</q><span class="gloss">{ltr_ranges(he)}</span></li>'
            for en, he in groups[g])
        out.append(f'<h3>{g}</h3><ul class="pcards">{items}</ul>')
    return ('<section class="chapter park-gen" id="phrases"><header class="ch-head"><span class="ch-no">EN</span>'
            '<h2>שיחון: מה אומרים ל‑Cast Members</h2></header><div class="ch-body">'
            '<p>כל המשפטים מהספר, מקובצים לפי מצב. אומרים אותם כמו שהם, באנגלית. התרגום מתחת הוא רק כדי לדעת מה אמרתם.</p>'
            + "".join(out) + "</div></section>")


def checklist(html_in):
    soup = BeautifulSoup(html_in, "html.parser")
    for li in soup.select(".ch-body li"):
        if li.find_parent(class_="tbl"):
            continue
        key = hashlib.sha1(li.get_text().encode()).hexdigest()[:10]
        label = soup.new_tag("label", attrs={"class": "chk"})
        box = soup.new_tag("input", attrs={"type": "checkbox", "id": f"c{key}", "data-key": key})
        span = soup.new_tag("span")
        for c in list(li.contents):
            if getattr(c, "name", None) in ("ul", "ol"):
                continue
            span.append(c.extract())
        label.append(box)
        label.append(span)
        li.insert(0, label)
        li["class"] = ["chk-li"]
    return str(soup)


def cover_svg():
    import math
    lines = []
    for cx, cy, r, n, col in [(70, 60, 44, 14, "var(--mk2)"), (215, 38, 26, 10, "#fff"), (300, 82, 34, 12, "var(--mk2)")]:
        for i in range(n):
            a = 2 * math.pi * i / n
            x1, y1 = cx + r * 0.35 * math.cos(a), cy + r * 0.35 * math.sin(a)
            x2, y2 = cx + r * math.cos(a), cy + r * math.sin(a)
            lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" />')
        lines.append(f'<circle cx="{cx}" cy="{cy}" r="2.5" fill="{col}" />')
    return ('<svg class="bursts" viewBox="0 0 360 130" aria-hidden="true" stroke-width="1.6" stroke-linecap="round">'
            + "".join(lines) + "</svg>")


def main():
    md = SRC.read_text(encoding="utf-8")
    ch = split_chapters(md)
    phrases = []
    parts = []

    glance = chapter_html(1, ch[1], phrases) + chapter_html(2, ch[2], phrases)
    parts.append(f'<div id="glance" class="part"><h2 class="part-title">הטיול במבט אחד</h2>{glance}</div>')
    parts.append(f'<div id="booking" class="part">{chapter_html(3, ch[3], phrases, "booking")}</div>')

    days = "".join(chapter_html(n, ch[n], phrases, "day", day_header(DAYS[n])).replace(f'id="ch{n}"', f'id="{DAYS[n]["id"]}"')
                   for n in (4, 5, 6))
    parts.append(f'<div class="part"><h2 class="part-title">הימים</h2>{days}</div>')

    toc = "".join(f'<li><a href="#ch{n}"><span class="n" dir="ltr">{n}</span> {ch[n]["title"]}</a></li>' for n in TOOLBOX)
    tools = "".join(chapter_html(n, ch[n], phrases) for n in TOOLBOX)
    parts.append(f'<div id="toolbox" class="part"><h2 class="part-title">ארגז הכלים</h2>'
                 f'<nav class="toc" aria-label="פרקי ארגז הכלים"><ol>{toc}</ol></nav>{tools}</div>')

    parts.append(phrasebook(phrases))
    parts.append(f'<div id="checklists" class="part">{checklist(chapter_html(22, ch[22], phrases, "checks"))}</div>')
    parts.append(f'<div id="rules" class="part">{chapter_html(21, ch[21], phrases, "rules")}</div>')

    tpl = (ROOT / "build" / "template.html").read_text(encoding="utf-8")
    page = tpl.replace("{{COVER_SVG}}", cover_svg()).replace("{{CONTENT}}", "\n".join(parts))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT} ({len(page):,} chars, {len(set(p for _, p in phrases))} phrases)")


if __name__ == "__main__":
    main()
