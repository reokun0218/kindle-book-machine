# epub_builder.py — builds the EPUB file using ebooklib
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import os
import re
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from ebooklib import epub

OUTPUT_DIR = Path("output")
CSS_PATH = Path("styles/kindle.css")

NUM_WORDS_EN = {
    1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five",
    6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten",
    11: "Eleven", 12: "Twelve", 13: "Thirteen", 14: "Fourteen", 15: "Fifteen"
}

NUM_KANJI = {
    1: "一", 2: "二", 3: "三", 4: "四", 5: "五",
    6: "六", 7: "七", 8: "八", 9: "九", 10: "十",
    11: "十一", 12: "十二", 13: "十三", 14: "十四", 15: "十五"
}


def clean_text(text):
    """Convert typography and escape XML special characters."""
    if not text:
        return ""
    # Em dash and ellipsis
    text = text.replace("--", "\u2014")
    text = text.replace("...", "\u2026")
    # Smart quotes (use actual Unicode chars, not escape sequences in replacement)
    text = re.sub(r'"([^"]*)"', '\u201c\\1\u201d', text)
    text = re.sub(r"'([^']*)'", '\u2018\\1\u2019', text)
    # XML escaping (order matters: & first)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def _markdown_to_html(text):
    """Convert basic markdown (**bold**, *italic*, ---) to HTML."""
    # Bold: **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Italic: *text*
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # Horizontal rule: --- or —- on its own line
    text = re.sub(r'^[-—]{2,}\s*$', '<hr/>', text, flags=re.MULTILINE)
    return text


def text_to_html_paragraphs(text, first_class="chapter-start"):
    """Split text on double newlines and wrap in <p> tags."""
    if not text:
        return "<p class=\"chapter-start\"></p>"
    paragraphs = text.split("\n\n")
    parts = []
    first = True
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        cleaned = clean_text(para)
        cleaned = _markdown_to_html(cleaned)
        # Preserve single newlines as <br/>
        cleaned = cleaned.replace("\n", "<br/>")
        if cleaned == "<hr/>":
            parts.append("<hr/>")
        elif first:
            parts.append(f'<p class="{first_class}">{cleaned}</p>')
            first = False
        else:
            parts.append(f'<p>{cleaned}</p>')
    return "\n".join(parts) if parts else "<p class=\"chapter-start\"></p>"


def _xhtml_page(title, body_html, lang="en", css_ref="../styles/kindle.css"):
    """Wrap body HTML in a full XHTML document."""
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{lang}" lang="{lang}">
<head>
  <meta charset="utf-8"/>
  <title>{clean_text(title)}</title>
  <link rel="stylesheet" type="text/css" href="{css_ref}"/>
</head>
<body>
{body_html}
</body>
</html>"""


def create_epub(book_data, output_filename):
    """Build and save the EPUB file. Returns the output file path."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    language = book_data.get("language", "english")
    lang_code = "ja" if language == "japanese" else "en"

    book = epub.EpubBook()
    book.set_identifier(str(uuid.uuid4()))
    book.set_title(book_data["title"])
    book.set_language(lang_code)
    book.add_author(book_data.get("author_display_name", "Unknown Author"))
    book.add_metadata("DC", "description", book_data.get("kdp_description", "")[:500])
    book.add_metadata("DC", "date", str(datetime.now().year))

    # Load and attach kindle.css
    try:
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            css_content = f.read()
    except FileNotFoundError:
        css_content = "body { font-family: Georgia, serif; line-height: 1.6; }"

    css_item = epub.EpubItem(
        uid="style_kindle",
        file_name="styles/kindle.css",
        media_type="text/css",
        content=css_content.encode("utf-8")
    )
    book.add_item(css_item)

    spine_items = ["nav"]
    toc_items = []

    # ── 1. Title page ────────────────────────────────────────────────────────
    subtitle = book_data.get("subtitle", "")
    author = book_data.get("author_display_name", "")
    subtitle_html = f'<p class="subtitle">{clean_text(subtitle)}</p>' if subtitle else ""
    title_body = f"""<div class="title-page">
  <h1>{clean_text(book_data["title"])}</h1>
  {subtitle_html}
  <p class="author">{clean_text(author)}</p>
</div>"""
    title_page = epub.EpubHtml(
        title="Title Page",
        file_name="title_page.xhtml",
        lang=lang_code
    )
    title_page.content = _xhtml_page("Title Page", title_body, lang_code).encode("utf-8")
    title_page.add_item(css_item)
    book.add_item(title_page)
    spine_items.append(title_page)

    # ── 2. Copyright page ────────────────────────────────────────────────────
    year = datetime.now().year
    copyright_body = f"""<div class="copyright-page">
  <p>Copyright &copy; {year} {clean_text(author)}</p>
  <p>All rights reserved.</p>
  <p>No part of this publication may be reproduced or transmitted in any form without written permission from the author.</p>
</div>"""
    copyright_page = epub.EpubHtml(
        title="Copyright",
        file_name="copyright.xhtml",
        lang=lang_code
    )
    copyright_page.content = _xhtml_page("Copyright", copyright_body, lang_code).encode("utf-8")
    copyright_page.add_item(css_item)
    book.add_item(copyright_page)
    spine_items.append(copyright_page)

    # ── 3. Table of Contents page ─────────────────────────────────────────────
    chapters = book_data.get("chapters", [])

    if language == "japanese":
        toc_heading = "目次"
        intro_label = "はじめに"
        conclusion_label = "おわりに"
    else:
        toc_heading = "Table of Contents"
        intro_label = "Introduction"
        conclusion_label = "Conclusion"

    toc_links = f'<li><a href="introduction.xhtml">{intro_label}</a></li>\n'
    for ch in chapters:
        num = ch["number"]
        if language == "japanese":
            ch_label = f"第{NUM_KANJI.get(num, str(num))}章：{ch['title']}"
        else:
            ch_label = f"Chapter {NUM_WORDS_EN.get(num, str(num))}: {ch['title']}"
        toc_links += f'<li><a href="chapter_{num:02d}.xhtml">{clean_text(ch_label)}</a></li>\n'
    toc_links += f'<li><a href="conclusion.xhtml">{conclusion_label}</a></li>\n'

    toc_body = f"""<div>
  <h1>{toc_heading}</h1>
  <ul>
  {toc_links}
  </ul>
</div>"""
    toc_page = epub.EpubHtml(
        title=toc_heading,
        file_name="toc_page.xhtml",
        lang=lang_code
    )
    toc_page.content = _xhtml_page(toc_heading, toc_body, lang_code).encode("utf-8")
    toc_page.add_item(css_item)
    book.add_item(toc_page)
    spine_items.append(toc_page)

    # ── 4. Introduction ───────────────────────────────────────────────────────
    intro_html = text_to_html_paragraphs(book_data.get("introduction", ""))
    intro_body = f"<h1>{intro_label}</h1>\n{intro_html}"
    intro_page = epub.EpubHtml(
        title=intro_label,
        file_name="introduction.xhtml",
        lang=lang_code
    )
    intro_page.content = _xhtml_page(intro_label, intro_body, lang_code).encode("utf-8")
    intro_page.add_item(css_item)
    book.add_item(intro_page)
    spine_items.append(intro_page)
    toc_items.append(epub.Link("introduction.xhtml", intro_label, "introduction"))

    # ── 5. Chapters ───────────────────────────────────────────────────────────
    for ch in chapters:
        num = ch["number"]
        if language == "japanese":
            ch_heading = f"第{NUM_KANJI.get(num, str(num))}章"
            ch_subtitle = ch["title"]
        else:
            ch_heading = f"Chapter {NUM_WORDS_EN.get(num, str(num))}"
            ch_subtitle = ch["title"]

        ch_html = text_to_html_paragraphs(ch.get("content", ""))
        ch_body = f"<h1>{clean_text(ch_heading)}</h1>\n<h2>{clean_text(ch_subtitle)}</h2>\n{ch_html}"
        ch_page = epub.EpubHtml(
            title=f"{ch_heading}: {ch['title']}",
            file_name=f"chapter_{num:02d}.xhtml",
            lang=lang_code
        )
        ch_page.content = _xhtml_page(ch["title"], ch_body, lang_code).encode("utf-8")
        ch_page.add_item(css_item)
        book.add_item(ch_page)
        spine_items.append(ch_page)
        toc_items.append(epub.Link(f"chapter_{num:02d}.xhtml", f"{ch_heading}: {ch['title']}", f"chapter{num:02d}"))

    # ── 6. Conclusion ─────────────────────────────────────────────────────────
    conclusion_html = text_to_html_paragraphs(book_data.get("conclusion", ""))
    conclusion_body = f"<h1>{conclusion_label}</h1>\n{conclusion_html}"
    conclusion_page = epub.EpubHtml(
        title=conclusion_label,
        file_name="conclusion.xhtml",
        lang=lang_code
    )
    conclusion_page.content = _xhtml_page(conclusion_label, conclusion_body, lang_code).encode("utf-8")
    conclusion_page.add_item(css_item)
    book.add_item(conclusion_page)
    spine_items.append(conclusion_page)
    toc_items.append(epub.Link("conclusion.xhtml", conclusion_label, "conclusion"))

    # ── 7. About the Author ───────────────────────────────────────────────────
    if language == "japanese":
        about_label = "著者について"
        about_body_html = f"""<div>
  <h1>{about_label}</h1>
  <p class="chapter-start">[著者名] は [職業・肩書き] です。[著者の簡単な紹介をここに入れてください。]</p>
  <p>お問い合わせ: [メールアドレス]</p>
  <p>ウェブサイト: [ウェブサイトURL]</p>
</div>"""
    else:
        about_label = "About the Author"
        about_body_html = f"""<div>
  <h1>{about_label}</h1>
  <p class="chapter-start">[AUTHOR NAME] is a [title/profession]. [Add a short 2-3 sentence bio here describing your background and why you wrote this book.]</p>
  <p>Connect: [email or website]</p>
</div>"""

    about_page = epub.EpubHtml(
        title=about_label,
        file_name="about_author.xhtml",
        lang=lang_code
    )
    about_page.content = _xhtml_page(about_label, about_body_html, lang_code).encode("utf-8")
    about_page.add_item(css_item)
    book.add_item(about_page)
    spine_items.append(about_page)

    # ── Navigation ────────────────────────────────────────────────────────────
    book.toc = toc_items
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine_items

    # ── Write file ────────────────────────────────────────────────────────────
    safe_name = output_filename.replace(" ", "_")
    if not safe_name.endswith(".epub"):
        safe_name += ".epub"
    out_path = OUTPUT_DIR / safe_name

    # epub3_pages=False avoids lxml parse error on Python 3.14
    epub.write_epub(str(out_path), book, {"epub3_pages": False})

    # ── Validate ──────────────────────────────────────────────────────────────
    assert out_path.exists(), "EPUB file was not created"
    assert out_path.stat().st_size > 0, "EPUB file is empty"
    assert zipfile.is_zipfile(str(out_path)), "EPUB is not a valid zip file"

    with zipfile.ZipFile(str(out_path)) as z:
        xhtml_files = [n for n in z.namelist() if n.endswith(".xhtml")]
        assert len(xhtml_files) > 0, "EPUB contains no .xhtml files"

    size_kb = out_path.stat().st_size // 1024
    print(f"✅ EPUB created: {out_path} ({size_kb}KB)")
    return str(out_path)
