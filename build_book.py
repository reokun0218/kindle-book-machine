# build_book.py — orchestrates the full book pipeline
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from book_generator import generate_full_book
from docx_builder import create_docx
from kdp_optimizer import generate_kdp_sheet
from pathlib import Path
import unicodedata, re


def _safe_filename(title):
    """ASCII-safe filename matching book_generator.py logic."""
    safe = title.replace(" ", "_")
    safe = "".join(
        c if c.isascii() and (c.isalnum() or c in "_-") else "_"
        for c in safe
    ).strip("_") or "book"
    return safe


def complete_book_pipeline(book_details, author_name, progress_callback=None):
    """
    Run the full pipeline: generate book → build DOCX → create KDP sheet.

    Returns:
        dict with keys: docx_path, kdp_sheet_path, json_path, stats
    """

    def update(pct, msg):
        if progress_callback:
            progress_callback(pct, msg)
        print(f"[{pct}%] {msg}")

    update(5, "Loading author profile...")

    # Generate full book text
    book_data = generate_full_book(book_details, author_name)

    # Use the actual path saved by generate_full_book (ASCII-safe)
    json_path = book_data.get("_final_json_path",
                              str(Path("output") / f"{_safe_filename(book_details['title'])}_final.json"))

    safe_title = _safe_filename(book_details["title"])

    update(85, "Wordファイルを作成中...")
    docx_path = create_docx(book_data, safe_title)

    update(93, "KDPシートを作成中...")
    kdp_sheet_path = generate_kdp_sheet(book_data, safe_title)

    update(100, "🎉 完成！")

    chapters = book_data.get("chapters", [])
    stats = {
        "total_words":     book_data.get("total_words", 0),
        "estimated_pages": book_data.get("estimated_pages", 0),
        "chapters":        len(chapters),
        "language":        book_data.get("language", "english"),
        "title":           book_data.get("title", ""),
        "subtitle":        book_data.get("subtitle", ""),
        "chapter_preview": chapters[0].get("content", "")[:400] if chapters else ""
    }

    return {
        "docx_path":      docx_path,
        "kdp_sheet_path": kdp_sheet_path,
        "json_path":      json_path,
        "stats":          stats
    }
