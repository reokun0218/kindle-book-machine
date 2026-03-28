# Kindle Book Machine — Build Instructions

## What this project is
A one-click Kindle book creator web app built with Python + Flask.

**What it does:**
- User uploads writing samples from any author
- App analyzes the writing style using Claude API
- User fills in book details (title, topic, audience, chapters)
- One button generates a complete book in that author's exact voice
- Outputs a KDP-ready EPUB + pre-filled Amazon upload sheet
- Supports both English and Japanese books

---

## YOUR JOB
Build ALL of the files listed below, completely, one after another.
Do not stop. Do not ask questions. Work autonomously until every file is built and tested.
If you hit an error, fix it yourself and continue.

---

## SETUP COMMANDS TO RUN FIRST

1. Run this to install Python libraries:
```
pip install flask==3.0.0 anthropic==0.25.0 ebooklib==0.18 python-dotenv==1.0.0 werkzeug==3.0.1 beautifulsoup4==4.12.2 lxml==5.1.0 Pillow==10.2.0
```

2. Create these folders if they don't exist:
   - templates/
   - static/
   - styles/
   - uploads/
   - output/
   - profiles/

3. Create a file called `.env` with:
```
ANTHROPIC_API_KEY=REPLACE_WITH_YOUR_KEY
FLASK_SECRET_KEY=kindle_app_secret_key_2024
```

---

## FILE 1: style_analyzer.py

Load API key from .env. Use UTF-8 encoding everywhere for Japanese support.

### Functions to build:

**load_writing_samples(file_paths)**
- Reads .txt, .md, .html files (strip HTML tags with BeautifulSoup for .html)
- Combines all text with double newlines between files
- Prints word count after loading
- If under 200 words, prints: "⚠️ Small sample — provide 500+ words for best results"
- Returns combined text string

**analyze_style_with_claude(text)**
- Sends first 8000 characters to claude-sonnet-4-20250514
- System prompt: "You are a world-class literary analyst and ghostwriter. Analyze writing samples and extract the author's unique voice with extreme precision."
- User prompt asks Claude to return ONLY a valid JSON object with these exact keys:
  - sentence_length: "short" / "medium" / "long"
  - avg_sentence_words: number
  - vocabulary_level: "simple" / "moderate" / "advanced"
  - tone_adjectives: list of 4 adjectives
  - uses_metaphors: true/false
  - metaphor_style: 15-word description
  - uses_personal_stories: true/false
  - uses_questions: true/false
  - paragraph_length: "very short" / "short" / "medium" / "long"
  - formality: "very casual" / "casual" / "semi-formal" / "formal"
  - emotional_style: one sentence
  - writing_rhythm: one sentence
  - unique_phrases: list of 5 actual phrases from the text
  - opening_style: one sentence
  - closing_style: one sentence
  - talks_to_reader: true/false
  - language: "english" / "japanese" / "mixed"
  - keigo_level: "n/a" / "casual" / "polite" / "formal" / "very formal"
  - cultural_patterns: 20-word description
- Parse JSON and return as Python dict
- If JSON parse fails, retry once, then return safe defaults

**create_writing_instructions(style_profile)**
- Converts the profile dict into one paragraph of writing instructions
- Example: "Write in a warm, reflective tone. Use short sentences averaging 12 words. Keep paragraphs short (3-4 sentences). Include personal stories and metaphors..."
- Covers all key profile attributes
- Returns the instruction string

**generate_style_preview(style_profile)**
- Calls Claude to write ONE paragraph on: "the moment I realized that growth begins with accepting where you are"
- Uses writing instructions from create_writing_instructions()
- System: "You are a professional ghostwriter. Write exactly in the style described."
- Returns the paragraph text only

**save_profile(style_profile, author_name, writing_instructions)**
- Saves to profiles/[author_name]_profile.json
- JSON includes both style_profile dict AND writing_instructions string
- Creates profiles/ folder if missing
- Prints: "✅ Profile saved: profiles/[author_name]_profile.json"

**load_profile(author_name)**
- Loads profiles/[author_name]_profile.json
- Returns tuple: (style_profile_dict, writing_instructions_string)
- Returns (None, None) if not found, prints friendly error

**list_saved_profiles()**
- Scans profiles/ folder for *_profile.json files
- Returns list of author names (without _profile.json suffix)

**analyze_author(file_paths, author_name)**
- THE MAIN FUNCTION
- Calls: load_writing_samples → analyze_style_with_claude → create_writing_instructions → generate_style_preview → save_profile
- Prints progress with emoji at each step
- Returns: (style_profile, writing_instructions, preview_paragraph)

### Test at the bottom (if __name__ == "__main__"):
- Create uploads/test_sample.txt with 200 words of self-help style writing
- Run analyze_author on it with name "Test_Author"
- Print the JSON profile and preview paragraph

---

## FILE 2: book_generator.py

Import load_profile from style_analyzer. Load API key from .env.

### Functions to build:

**generate_outline(book_details, writing_instructions, client)**
- Asks Claude to create a book outline
- Returns JSON with: subtitle (max 10 words), chapter_titles (list of N titles), introduction_theme, conclusion_theme
- Chapter titles must be EMOTIONAL not academic
  - BAD: "Chapter 1: Understanding Change"
  - GOOD: "The Night Everything Changed"
- If JSON parse fails, return safe default outline

**generate_introduction(book_details, outline, writing_instructions, client)**
- Writes 500-700 word book introduction
- Must open with a specific moment or image (not "In this book I will...")
- Must make reader feel: "this book was written for me"
- Speaks directly to the target audience's pain or longing
- Returns intro text string

**generate_chapter(chapter_num, chapter_title, book_details, previous_summary, writing_instructions, client)**
- Writes one complete chapter
- Structure: opening hook → 3 sections → closing reflection
- Rules enforced in prompt:
  - Never use the word "journey"
  - Address reader as "you" at least 3 times
  - At least one personal story or vulnerable moment
  - Vary sentence length throughout
- If language is "japanese": write entirely in Japanese, use 第[N]章 format for chapter number references
- After writing chapter, makes SECOND API call to generate 2-sentence summary
- Returns tuple: (chapter_content_string, summary_string)

**generate_conclusion(book_details, all_summaries, writing_instructions, client)**
- all_summaries is a list of all chapter summaries joined with newlines
- Writes 500-700 word conclusion
- Does NOT summarize chapter by chapter
- Feels like a heartfelt letter from a trusted friend
- Ends with one thing the reader can do or see differently
- Returns conclusion text string

**generate_kdp_metadata(book_details, client)**
- Returns dict with:
  - kdp_description: 400-word Amazon description starting with a hook
  - kdp_keywords: list of exactly 7 keywords people actually search for
  - bisac_primary: BISAC code + description (e.g. "SEL016000 — Self-Help / Personal Growth")
  - bisac_secondary: second BISAC code + description
- If language is "japanese": keywords should be Japanese search terms

**generate_full_book(book_details, author_name)**
- THE MAIN FUNCTION
- Loads profile with load_profile(author_name)
- If profile not found: raises ValueError with friendly message
- Calls all functions in order
- After each chapter: saves draft to output/[title]_draft.json (crash protection)
- Prints progress percentage after each step: "[25%] ✅ Chapter 1 of 4 complete"
- On API rate limit error: waits 30 seconds and retries automatically
- Returns complete book dictionary:
  {
    title, subtitle, author_display_name,
    introduction, chapters (list of {number, title, content, summary}),
    conclusion, kdp_description, kdp_keywords,
    bisac_primary, bisac_secondary,
    total_words, estimated_pages, language
  }

**book_details format:**
```python
{
  "title": "...",
  "topic": "...",
  "audience": "...",
  "chapters": 8,
  "words_per_chapter": 1500,
  "language": "english",
  "author_display_name": "..."
}
```

---

## FILE 3: styles/kindle.css

KDP-safe CSS ONLY. Keep under 60 lines.

Rules:
- body: Georgia serif, font-size 1em, line-height 1.6, text-align justify, margin/padding 0
- h1: centered, large (1.8em), bold, page-break-before always, margin-top 3em
- h2: 1.3em, bold, margin-top 1.5em
- p: text-indent 1.5em, margin 0, padding 0
- p.chapter-start: text-indent 0, margin-top 1em (first para after heading)
- .title-page: text-align center, margin-top 5em
- .copyright-page: font-size 0.85em, margin-top 8em, text-align center
- blockquote: margin 0 2em, font-style italic
- hr: border-top 1px solid #999, margin 1.5em 2em, border 0

FORBIDDEN: flexbox, CSS grid, fixed pixel widths, hex color codes in body text, rgba colors

---

## FILE 4: epub_builder.py

Use ebooklib library.

**clean_text(text)**
- Converts `--` to `—` (em dash)
- Converts `...` to `…` (ellipsis)
- Converts straight quotes to smart quotes (open/close)
- Escapes XML special chars: & → &amp; < → &lt; > → &gt;
- Returns cleaned string

**text_to_html_paragraphs(text, first_class="chapter-start")**
- Splits on double newlines
- Strips each paragraph
- Skips empty paragraphs
- First paragraph gets class=first_class
- All others get class="p" (actually no class needed, just plain p tags)
- Returns HTML string of p tags

**create_epub(book_data, output_filename)**
- Creates epub.Book object
- Sets metadata: title, author (author_display_name), language (en/ja), identifier (uuid), description (first 500 chars of kdp_description), date (current year)
- Reads styles/kindle.css and adds as EpubItem
- Creates pages in this order:
  1. Title page (.title-page div with title, subtitle, author)
  2. Copyright page (.copyright-page div)
  3. HTML Table of Contents page (lists all chapters)
  4. Introduction page
  5. All chapter pages (chapter_{num:02d}.xhtml)
  6. Conclusion page
  7. About Author page (placeholder with [AUTHOR NAME] etc.)
- Each page: proper XHTML with xml declaration, html tag with xmlns and lang attribute
- All pages link to kindle.css: `<link rel="stylesheet" type="text/css" href="../styles/kindle.css"/>`
- Chapter headings use English "Chapter One:" format or Japanese 第一章 based on language
- Adds EpubNcx and EpubNav
- Sets spine in order
- Saves to output/[output_filename].epub
- Validates: file exists, size > 0, is valid zip, contains .xhtml files
- Prints: "✅ EPUB created: output/[filename].epub ([size]KB)"
- Returns the output file path

---

## FILE 5: kdp_optimizer.py

**generate_kdp_sheet(book_data, output_filename)**
- Creates output/[output_filename]_KDP_SHEET.txt
- Format:

```
════════════════════════════════════
📚 KDP UPLOAD SHEET
Generated: [date time]
════════════════════════════════════

BOOK TITLE:
[title]

SUBTITLE:
[subtitle]

AUTHOR NAME:
[author_display_name]

SERIES: (leave blank)
EDITION NUMBER: 1

DESCRIPTION — copy this into KDP (4000 char limit):
────────────────────────────────────
[kdp_description]
────────────────────────────────────
Character count: [count] / 4000

KEYWORDS (enter one per box in KDP):
1. [keyword 1]
2. [keyword 2]
3. [keyword 3]
4. [keyword 4]
5. [keyword 5]
6. [keyword 6]
7. [keyword 7]

PRIMARY CATEGORY:
[bisac_primary]

SECONDARY CATEGORY:
[bisac_secondary]

════════════════════════════════════
PRICING SUGGESTION
════════════════════════════════════
Your word count: [total_words]

Kindle pricing guide (70% royalty range: $2.99–$9.99):
• Under 10,000 words → $2.99
• 10,000–25,000 words → $4.99
• 25,000–40,000 words → $6.99
• Over 40,000 words → $7.99–$9.99

Suggested price: $[calculated based on word count]

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
```

- Returns the output file path

---

## FILE 6: build_book.py

**complete_book_pipeline(book_details, author_name, progress_callback=None)**

```python
def update(pct, msg):
    if progress_callback:
        progress_callback(pct, msg)
    print(f"[{pct}%] {msg}")
```

- update(5, "Loading author profile...")
- Calls generate_full_book() from book_generator
- update(80, "Building EPUB file...")
- Calls create_epub() from epub_builder — filename = title with spaces→underscores, lowercase
- update(90, "Creating KDP upload sheet...")
- Calls generate_kdp_sheet() from kdp_optimizer
- update(100, "🎉 Complete!")
- Returns dict: {epub_path, kdp_sheet_path, json_path, stats}

---

## FILE 7: app.py

Flask web server.

```python
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
import os, json, threading
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev")
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

generation_status = {
    "running": False, "progress": 0,
    "message": "Ready", "error": None, "output_files": {}
}
```

**Routes:**

`GET /`
- Imports list_saved_profiles from style_analyzer
- Renders templates/index.html with saved_profiles list

`POST /analyze-style`
- Gets author_name from form
- Gets files from request.files.getlist("samples")
- Returns error JSON if no files
- Saves files to uploads/ using werkzeug secure_filename
- Calls analyze_author(file_paths, author_name) from style_analyzer
- Returns: {success: true, author_name, preview_paragraph, message}
- On error: {success: false, error: message}

`POST /generate-book`
- If generation_status["running"]: return error
- Parses: title, topic, audience, chapters (int), words_per_chapter (int), language, author_name, author_display_name
- Sets generation_status running=True, progress=0
- Starts background thread: threading.Thread(target=run_generation, args=(book_details,))
- Returns: {success: true}

`GET /status`
- Returns generation_status as JSON

`GET /download/<file_type>`
- file_type: "epub" or "kdp_sheet"
- Gets path from generation_status["output_files"]
- Returns file with send_file as attachment
- Returns 404 if not found

`GET /list-profiles`
- Returns {profiles: list_saved_profiles()}

**run_generation(book_details) function:**
```python
def run_generation(book_details):
    global generation_status
    try:
        def update(pct, msg):
            generation_status["progress"] = pct
            generation_status["message"] = msg
        
        from build_book import complete_book_pipeline
        output_files = complete_book_pipeline(
            book_details,
            book_details["author_name"],
            progress_callback=update
        )
        generation_status["output_files"] = output_files
        generation_status["running"] = False
    except Exception as e:
        generation_status["error"] = str(e)
        generation_status["running"] = False
        generation_status["message"] = f"❌ Error: {str(e)}"
```

---

## FILE 8: templates/index.html

Single-page web app. Links to /static/style.css.

**Section 1 — "Set the Author's Voice"**
- Multiple file upload input (accept=".txt,.md,.html", multiple)
- Text input: profile_name placeholder "e.g. Reo_Flowing_Life"
- Select dropdown for saved profiles (populated from Flask template variable)
- Button: "Analyze Writing Style" → calls /analyze-style via fetch
- Loading state: "Analyzing style... this takes 30 seconds"
- Result area (hidden until done): shows preview paragraph with label "This is how your book will sound:"

**Section 2 — "Your Book Details"** (opacity 0.4 until style analyzed, then enabled)
- Input: book title
- Textarea (3 rows): book topic
- Input: target audience, placeholder "e.g. Women 35-55 rebuilding after divorce"
- Select: chapters (options: 2, 3, 5, 8, 10, 12)
- Select: words per chapter (options: 400, 600, 800, 1000, 1500, 2000)
- Select: language (English, Japanese 日本語)
- Input: author display name (appears on book cover)
- Big button: "🚀 Generate My Book"

**Progress section** (hidden until generation starts):
- H3: "Writing your book..."
- Progress bar div with percentage
- Status message paragraph

**Results section** (hidden until complete):
- H2: "🎉 Your Book is Ready!"
- 3 stat boxes: word count, estimated pages, reading time
- Orange button: "📥 Download EPUB" → /download/epub
- Outlined button: "📋 Download KDP Sheet" → /download/kdp_sheet
- Preview div showing first 400 chars of chapter 1

**JavaScript (vanilla):**

Style form submit:
```javascript
formEl.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData();
  // add files and author_name
  showLoading("Analyzing style...");
  const res = await fetch('/analyze-style', {method:'POST', body:fd});
  const data = await res.json();
  if (data.success) {
    showPreview(data.preview_paragraph);
    enableSection2();
  } else {
    showError(data.error);
  }
});
```

Generate button:
```javascript
// POST book details to /generate-book
// Start polling /status every 3 seconds
// Update progress bar
// When progress == 100, show results section
// Fetch /status to get output_files, then show download buttons
// Also show first 400 chars of chapter 1 from preview endpoint
```

Add a `/preview` route to app.py that returns intro+first chapter preview from the saved JSON.

Error handling: show errors in red, add "Try Again" button that resets to initial state.

---

## FILE 9: static/style.css

Clean professional design.

- body: background #0f1117, font "Plus Jakarta Sans" or system sans, color #e8eaf0
- .container: max-width 820px, margin auto, padding 20px
- .section: background #1a1f2e, border-radius 16px, padding 28px, margin-bottom 20px, border 1px solid #2a3045
- h1: font-size 28px, font-weight 800, margin-bottom 4px
- h2: font-size 20px, font-weight 700
- label: display block, font-size 13px, font-weight 600, margin-bottom 6px, color #8892a4
- input, textarea, select: width 100%, padding 10px 14px, background #0d1117, border 1px solid #2a3045, border-radius 8px, color #e8eaf0, font-size 14px, margin-bottom 16px
- input:focus, textarea:focus, select:focus: border-color #6366f1, outline none
- .btn-primary: background #6366f1, color white, border none, padding 14px 28px, border-radius 10px, font-size 15px, font-weight 700, cursor pointer, width 100%, margin-top 8px
- .btn-primary:hover: background #4f46e5
- .btn-secondary: background transparent, border 1px solid #6366f1, color #6366f1, same padding as primary
- .progress-bar-wrap: background #0d1117, border-radius 8px, height 8px, overflow hidden, margin 16px 0
- .progress-bar: background #6366f1, height 100%, transition width 0.5s
- .stat-boxes: display grid, grid-template-columns repeat(3, 1fr), gap 12px, margin 20px 0
- .stat-box: background #0d1117, border-radius 10px, padding 16px, text-align center
- .stat-box .num: font-size 24px, font-weight 800, color #6366f1
- .stat-box .label: font-size 12px, color #8892a4
- .preview-text: background #0d1117, border-radius 10px, padding 16px, font-style italic, line-height 1.8, color #8892a4, margin-top 16px
- .error: background rgba(239,68,68,.1), border 1px solid rgba(239,68,68,.3), color #fca5a5, padding 14px, border-radius 10px
- Mobile: max-width 100%, single column stat-boxes under 600px

---

## FILE 10: START.py

```python
"""Run this to start the Kindle Book Machine."""
import subprocess, sys, os, webbrowser, threading, time

print("""
╔══════════════════════════════════════╗
║   📚  KINDLE BOOK MACHINE            ║
║   Starting up...                     ║
╚══════════════════════════════════════╝
""")

# Check .env exists
if not os.path.exists('.env'):
    print("❌ Missing .env file. Create it with your ANTHROPIC_API_KEY.")
    sys.exit(1)

# Create missing folders
for folder in ['uploads', 'output', 'profiles', 'templates', 'static', 'styles']:
    os.makedirs(folder, exist_ok=True)

print("✅ All folders ready")
print("🌐 Starting server...")
print("📖 Opening browser in 3 seconds...")
print("\nTo stop: press Ctrl+C\n")

def open_browser():
    time.sleep(3)
    webbrowser.open("http://localhost:5000")

threading.Thread(target=open_browser, daemon=True).start()
subprocess.run([sys.executable, "app.py"])
```

---

## TESTING — Run this after building all files

1. Run: `python START.py`
2. Confirm it opens http://localhost:5000
3. Run: `python style_analyzer.py` — should print a JSON profile and preview paragraph
4. Tell me: "All files complete" when done

---

## IMPORTANT RULES

- Use error handling (try/except) in every function
- Use UTF-8 encoding on every file read/write
- Load API key from .env using python-dotenv everywhere
- Claude API model to use: claude-sonnet-4-20250514
- If rate limited: wait 30 seconds and retry automatically
- Print friendly progress messages with emoji throughout
- Never ask me questions — figure it out and keep building
