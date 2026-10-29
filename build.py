#!/usr/bin/env python3
"""Build blog posts from Markdown notes (written in Obsidian) with Pandoc.

    python build.py                       build every post, the blog list, the home list and feed.xml
    python build.py new my-slug "Title"   start a new post (it begins as a draft)
"""
import datetime, html, re, shutil, subprocess, sys
from pathlib import Path
from urllib.parse import quote, unquote

SITE = "https://roushal.github.io"   # your site address, used in feed.xml
AUTHOR = "Raushal Shrestha"
POSTS = "posts"                       # the Obsidian vault; a path outside the repo also works
HOME_COUNT = 5                        # posts listed on the home page

ROOT = Path(__file__).resolve().parent
POSTS_DIR = Path(POSTS) if Path(POSTS).is_absolute() else ROOT / POSTS
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


# --- reading a note -------------------------------------------------------

def split_front_matter(text):
    """Return (settings, raw front matter, body). Simple `key: value` lines and `- item` lists only."""
    m = re.match(r"---\r?\n(.*?)\r?\n---[ \t]*\r?\n?", text, re.S)
    if not m:
        return {}, "", text
    meta, key = {}, None
    for line in m.group(1).splitlines():
        if re.match(r"\s*-\s+", line) and key:
            meta[key].append(line.split("-", 1)[1].strip().strip("'\""))
        elif ":" in line:
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip()
            if value.startswith("["):
                meta[key] = [v.strip().strip("'\"") for v in value.strip("[]").split(",") if v.strip()]
            else:
                meta[key] = value.strip("'\"").replace('\\"', '"') if value else []
    return meta, m.group(0).rstrip() + "\n", text[m.end():]


def embed(m):
    """![[file.png]] and ![[file.png|alt or width]] -> standard Markdown image."""
    name, extra = m.group(1).strip(), (m.group(2) or "").strip()
    if extra.isdigit():
        return f"![]({quote(name)}){{width={extra}}}"
    return f"![{extra}]({quote(name)})"


def prepare(body):
    """Turn Obsidian-only syntax into what Pandoc understands. Code and maths are left alone."""
    held = []

    def hold(m):
        held.append(m.group(0))
        return f"\x00{len(held) - 1}\x00"

    body = re.sub(r"%%.*?%%", "", body, flags=re.S)                                  # %% comments %%
    body = re.sub(r"^(```|~~~)[^\n]*\n.*?^\1[ \t]*$|`[^`\n]+`", hold, body, flags=re.S | re.M)
    body = re.sub(r"\$\$.*?\$\$|(?<![\\$])\$(?![\s$])[^$\n]+?(?<![\s\\])\$(?!\d)", hold, body, flags=re.S)
    body = re.sub(r"!\[\[([^\]|]+)(?:\|([^\]]*))?\]\]", embed, body)                 # ![[img.png|300]]
    body = re.sub(r"!\[([^\]|]*)\|(\d+)\]\(([^)]+)\)", r"![\1](\3){width=\2}", body)  # ![alt|300](img.png)
    body = re.sub(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]", lambda m: m.group(2) or m.group(1), body)
    body = re.sub(r"==(.+?)==", r"<mark>\1</mark>", body)                            # ==highlight==
    body = "\n".join(                                                                # -- becomes an em dash
        line if re.fullmatch(r"[\s|:\-]*", line) or "<!--" in line or "-->" in line
        else re.sub(r"(?<!-)--(?!-)", "—", line)
        for line in body.split("\n"))
    return re.sub(r"\x00(\d+)\x00", lambda m: held[int(m.group(1))], body)


# --- Pandoc and tidying ----------------------------------------------------

def pandoc(source, variables):
    cmd = ["pandoc", "-f", "markdown-implicit_figures+hard_line_breaks", "-t", "html5",
           "--mathml", "--no-highlight", "--wrap=none", "--template", str(ROOT / "templates" / "post.html")]
    for key, value in variables.items():
        cmd += ["-M", f"{key}={value}"]
    try:
        run = subprocess.run(cmd, input=source, capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        sys.exit("Pandoc is not installed. On Windows run:  winget install --id JohnMacFarlane.Pandoc")
    if run.returncode:
        raise RuntimeError(run.stderr.strip())
    return run.stdout


def figure(m):
    """A paragraph holding only an image becomes a <figure>. {.wide} widens it; a "title" becomes its caption."""
    img = m.group(1)
    classes = (re.search(r'\sclass="([^"]*)"', img) or [None, ""])[1].split()
    wide = "wide" in classes
    classes = [c for c in classes if c != "wide"]
    img = re.sub(r'\sclass="[^"]*"', f' class="{" ".join(classes)}"' if classes else "", img)
    caption = re.search(r'\stitle="([^"]*)"', img)
    img = re.sub(r'\stitle="[^"]*"', "", img)
    inner = img + (f"<figcaption>{caption.group(1)}</figcaption>" if caption else "")
    return f'<figure{" class=" + chr(34) + "wide" + chr(34) if wide else ""}>{inner}</figure>'


def tidy(page):
    page = re.sub(r"\s*<colgroup>.*?</colgroup>", "", page, flags=re.S)
    page = re.sub(r'<tr class="(?:odd|even|header)">', "<tr>", page)
    page = page.replace(" />", ">")
    return re.sub(r"<p>(<img [^>]*>)</p>", figure, page)


# --- dates, titles and lists ------------------------------------------------

def short_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def long_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day} {datetime.date(2000, d.month, 1).strftime('%B')} {d.year}"


def text(s):
    return html.escape(s.replace("'", "’"), quote=False)


def smart(s):
    """Curly quotes for values that go into <meta> attributes, where a straight " would end the attribute."""
    return re.sub(r'"([^"]*)"', r"“\1”", s).replace('"', "”").replace("'", "’")


def replace_list(path, pattern, posts, prefix):
    if not path.exists():
        return
    items = "\n".join(
        f'      <li>\n        <time class="when" datetime="{p["date"]}">{short_date(p["date"])}</time>\n'
        f'        <a href="{prefix}{p["slug"]}/index.html">{text(p["title"])}</a>\n      </li>' for p in posts)
    block = f'<ul class="log">\n{items}\n    </ul>'
    page = path.read_text(encoding="utf-8")
    page, n = re.subn(pattern, lambda m: m.group(1) + block, page, count=1, flags=re.S)
    if n:
        path.write_text(page, encoding="utf-8")
    else:
        print(f"warning: no <ul class=\"log\"> list found in {path.relative_to(ROOT)}; left unchanged")


def write_feed(posts):
    updated = f"{posts[0]['date']}T00:00:00+05:45" if posts else "2026-01-01T00:00:00+05:45"
    entries = "".join(f"""  <entry>
    <title>{text(p["title"])}</title>
    <link href="{SITE}/blog/{p["slug"]}/"/>
    <id>{SITE}/blog/{p["slug"]}/</id>
    <published>{p["date"]}T00:00:00+05:45</published>
    <updated>{p["updated"]}T00:00:00+05:45</updated>
    <summary>{text(p["description"])}</summary>
  </entry>
""" for p in posts)
    (ROOT / "feed.xml").write_text(f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>{AUTHOR}</title>
  <subtitle>Notes and essays.</subtitle>
  <link href="{SITE}/feed.xml" rel="self"/>
  <link href="{SITE}/"/>
  <id>{SITE}/</id>
  <updated>{updated}</updated>
  <author>
    <name>{AUTHOR}</name>
  </author>
{entries}</feed>
""", encoding="utf-8")


# --- building ---------------------------------------------------------------

def build_post(note):
    folder, slug = note.parent, note.parent.name
    meta, front, body = split_front_matter(note.read_text(encoding="utf-8-sig"))
    if str(meta.get("draft", "")).lower() == "true":
        print(f"draft  {slug} (skipped)")
        return None
    title, date = meta.get("title"), meta.get("date")
    if not title or not date:
        print(f"error  {slug}: front matter needs title and date")
        return None
    try:
        datetime.date.fromisoformat(date)
    except ValueError:
        print(f"error  {slug}: date must look like 2026-10-25, not '{date}'")
        return None
    updated = meta.get("updated") or date
    description = meta.get("description") or ""
    page = pandoc(front + "\n" + prepare(body), {
        "slug": slug, "date_human": long_date(date), "updated_human": long_date(updated),
        "title_attr": smart(title), "description_attr": smart(description)})
    out = ROOT / "blog" / slug
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(tidy(page), encoding="utf-8")
    for f in folder.rglob("*"):                                   # images and anything else beside the note
        if f.is_file() and f != note and not any(part.startswith(".") for part in f.relative_to(folder).parts):
            (out / f.relative_to(folder)).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, out / f.relative_to(folder))
    for src in re.findall(r'<(?:img|iframe)[^>]*\ssrc="([^"]+)"', tidy(page)):
        if not re.match(r"(https?:|data:|/)", src) and not (out / unquote(src)).exists():
            print(f"warning: {slug}: '{unquote(src)}' is not in the post folder")
    print(f"built  {slug}")
    return {"slug": slug, "title": title, "date": date, "updated": updated, "description": description}


def build():
    if not POSTS_DIR.is_dir():
        sys.exit(f"No posts folder at {POSTS_DIR}")
    posts = []
    for note in sorted(POSTS_DIR.glob("*/*.md")):
        if note.parent.name.startswith("."):
            continue
        if len(list(note.parent.glob("*.md"))) > 1:
            print(f"error  {note.parent.name}: keep one .md file per post folder")
            continue
        post = build_post(note)
        if post:
            posts.append(post)
    posts.sort(key=lambda p: p["date"], reverse=True)
    replace_list(ROOT / "blog" / "index.html", r'()<ul class="log">.*?</ul>', posts, "")
    replace_list(ROOT / "index.html", r'(<h2>Writing</h2>\s*)<ul class="log">.*?</ul>', posts[:HOME_COUNT], "blog/")
    write_feed(posts)
    if "USERNAME" in SITE:
        print("note: set SITE at the top of build.py to your address so feed.xml links work")


def new(slug, title):
    folder = POSTS_DIR / slug
    if folder.exists():
        sys.exit(f"{folder} already exists")
    folder.mkdir(parents=True)
    (folder / f"{slug}.md").write_text(
        f"---\ntitle: {title}\ndate: {datetime.date.today().isoformat()}\n"
        f"description: One sentence for link previews and the feed.\ndraft: true\n---\n\n", encoding="utf-8")
    print(f"created {folder / (slug + '.md')}  (remove 'draft: true' to publish)")


if __name__ == "__main__":
    if sys.argv[1:2] == ["new"] and len(sys.argv) == 4:
        new(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 1:
        build()
    else:
        sys.exit(__doc__)
