# kdp_optimizer.py — creates the Amazon KDP upload sheet
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path("output")


def _suggest_price(total_words):
    """Return a suggested Kindle price based on word count."""
    if total_words < 10000:
        return "$2.99"
    elif total_words < 25000:
        return "$4.99"
    elif total_words < 40000:
        return "$6.99"
    else:
        return "$7.99"


def generate_kdp_sheet(book_data, output_filename):
    """Create a pre-filled KDP upload sheet as a .txt file."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    title = book_data.get("title", "")
    subtitle = book_data.get("subtitle", "")
    author = book_data.get("author_display_name", "")
    description = book_data.get("kdp_description", "")
    keywords = book_data.get("kdp_keywords", [])
    bisac_primary = book_data.get("bisac_primary", "")
    bisac_secondary = book_data.get("bisac_secondary", "")
    total_words = book_data.get("total_words", 0)

    # Ensure 7 keywords
    while len(keywords) < 7:
        keywords.append("")
    keywords = keywords[:7]

    desc_count = len(description)
    suggested_price = _suggest_price(total_words)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    keyword_lines = "\n".join([f"{i+1}. {kw}" for i, kw in enumerate(keywords)])

    sheet = f"""════════════════════════════════════
📚 KDP UPLOAD SHEET
Generated: {now}
════════════════════════════════════

BOOK TITLE:
{title}

SUBTITLE:
{subtitle}

AUTHOR NAME:
{author}

SERIES: (leave blank)
EDITION NUMBER: 1

DESCRIPTION — copy this into KDP (4000 char limit):
────────────────────────────────────
{description}
────────────────────────────────────
Character count: {desc_count} / 4000

KEYWORDS (enter one per box in KDP):
{keyword_lines}

PRIMARY CATEGORY:
{bisac_primary}

SECONDARY CATEGORY:
{bisac_secondary}

════════════════════════════════════
PRICING SUGGESTION
════════════════════════════════════
Your word count: {total_words:,}

Kindle pricing guide (70% royalty range: $2.99–$9.99):
• Under 10,000 words → $2.99
• 10,000–25,000 words → $4.99
• 25,000–40,000 words → $6.99
• Over 40,000 words → $7.99–$9.99

Suggested price: {suggested_price}

════════════════════════════════════
UPLOAD CHECKLIST
════════════════════════════════════
□ EPUB file passes Kindle Previewer
□ Cover image is at least 1600×2560px JPG
□ Description is under 4,000 characters
□ All 7 keyword boxes filled in
□ 2 categories selected
□ Price is set in the $2.99–$9.99 range
□ "Enroll in KDP Select" — decide yes/no

════════════════════════════════════
"""

    safe_name = output_filename.replace(" ", "_")
    out_path = OUTPUT_DIR / f"{safe_name}_KDP_SHEET.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(sheet)

    print(f"✅ KDP sheet saved: {out_path}")
    return str(out_path)
