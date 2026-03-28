# book_generator.py — writes a complete book chapter by chapter using Claude API
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import os
import json
import time
import re
from pathlib import Path
from dotenv import load_dotenv
import anthropic
from style_analyzer import load_profile

load_dotenv(override=True)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

OUTPUT_DIR = Path("output")

NUM_WORDS = {
    1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five",
    6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten",
    11: "Eleven", 12: "Twelve", 13: "Thirteen", 14: "Fourteen", 15: "Fifteen"
}

NUM_KANJI = {
    1: "一", 2: "二", 3: "三", 4: "四", 5: "五",
    6: "六", 7: "七", 8: "八", 9: "九", 10: "十",
    11: "十一", 12: "十二", 13: "十三", 14: "十四", 15: "十五"
}


def _call_with_retry(fn, *args, **kwargs):
    """Call an API function, retrying once after 30s if rate limited."""
    for attempt in range(3):
        try:
            return fn(*args, **kwargs)
        except anthropic.RateLimitError:
            if attempt < 2:
                print("⏳ Rate limited — waiting 30 seconds...")
                time.sleep(30)
            else:
                raise
        except Exception as e:
            raise e


def generate_outline(book_details, writing_instructions, client):
    """Generate a book outline with emotional chapter titles."""
    title = book_details["title"]
    topic = book_details["topic"]
    audience = book_details["audience"]
    num_chapters = book_details["chapters"]
    language = book_details.get("language", "english")

    if language == "japanese":
        lang_instruction = "Respond entirely in Japanese. Chapter titles must be in Japanese."
    else:
        lang_instruction = "Respond in English."

    prompt = f"""Create a book outline for:
Title: {title}
Topic: {topic}
Target audience: {audience}
Number of chapters: {num_chapters}
{lang_instruction}

Return ONLY a valid JSON object with these exact keys:
{{
  "subtitle": "<max 10 words, compelling subtitle>",
  "chapter_titles": ["<title 1>", "<title 2>", ...],
  "introduction_theme": "<one sentence describing what the introduction covers>",
  "conclusion_theme": "<one sentence describing what the conclusion covers>"
}}

Chapter title rules:
- EMOTIONAL not academic
- BAD: "Chapter 1: Understanding Change"
- GOOD: "The Night Everything Changed"
- Each title must make the reader want to read that chapter
- Return exactly {num_chapters} chapter titles

Return ONLY the JSON. No markdown. No explanation."""

    safe_default = {
        "subtitle": f"A Guide to {topic}",
        "chapter_titles": [f"The Beginning of Everything" if i == 0 else f"The Path Forward {i+1}" for i in range(num_chapters)],
        "introduction_theme": "Setting the stage for transformation",
        "conclusion_theme": "Embracing the new you"
    }

    for attempt in range(3):
        try:
            response = _call_with_retry(
                client.messages.create,
                model="claude-sonnet-4-6",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response.content[0].text.strip()
            # Strip markdown code fences
            raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            # Extract JSON object even if surrounded by text
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                raw = match.group(0)
            parsed = json.loads(raw)
            # Validate we got real chapter titles
            titles = parsed.get("chapter_titles", [])
            if len(titles) >= num_chapters:
                return parsed
            print(f"⚠️ Outline returned {len(titles)} titles, expected {num_chapters} — retrying...")
        except json.JSONDecodeError as e:
            print(f"⚠️ Outline JSON parse failed (attempt {attempt+1}): {e}")
            if attempt < 2:
                time.sleep(5)
        except Exception as e:
            print(f"⚠️ Outline generation error: {e}")
            if attempt < 2:
                time.sleep(5)

    print("⚠️ Outline generation failed 3 times — using topic-based defaults")
    # Build meaningful defaults from the actual topic instead of generic placeholders
    if language == "japanese":
        default_titles = [f"{topic}の真実 第{i+1}章" for i in range(num_chapters)]
    else:
        default_titles = [f"The Truth About {topic} — Part {i+1}" for i in range(num_chapters)]
    safe_default["chapter_titles"] = default_titles
    return safe_default


def generate_introduction(book_details, outline, writing_instructions, client):
    """Write a 500-700 word book introduction."""
    language = book_details.get("language", "english")

    if language == "japanese":
        lang_note = "Write entirely in Japanese."
    else:
        lang_note = "Write in English."

    chapter_list  = "\n".join([f"- {t}" for t in outline.get("chapter_titles", [])])
    author_story  = book_details.get("author_story", "")
    main_message  = book_details.get("main_message", "")
    story_hint    = f"\nAuthor's real story to open with (use this as the emotional hook): {author_story}" if author_story else ""
    message_hint  = f"\nCore message: {main_message}" if main_message else ""

    prompt = f"""Write a book introduction for:
Title: {book_details['title']}
Subtitle: {outline.get('subtitle', '')}
Topic: {book_details['topic']}
Audience: {book_details['audience']}
Introduction theme: {outline.get('introduction_theme', '')}
{story_hint}
{message_hint}

Chapters include:
{chapter_list}

Writing style instructions:
{writing_instructions}

{lang_note}

Rules:
- 500–700 words
- If author's real story is provided, open with THAT specific moment — make it vivid and emotional
- Make the reader feel: "this book was written for me"
- Speak directly to the target audience's pain or longing
- End by hinting at the transformation ahead
- Do NOT list chapter summaries

Write only the introduction text. No title heading."""

    try:
        response = _call_with_retry(
            client.messages.create,
            model="claude-sonnet-4-6",
            max_tokens=1200,
            system=f"You are a professional ghostwriter writing in this exact style: {writing_instructions[:500]}",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"⚠️ Introduction error: {e}")
        return f"Introduction for {book_details['title']}.\n\n{book_details['topic']}"


def generate_chapter(chapter_num, chapter_title, book_details, previous_summary, writing_instructions, client):
    """Write one complete chapter. Returns (content, summary)."""
    language = book_details.get("language", "english")
    words_target = book_details.get("words_per_chapter", 1500)

    if language == "japanese":
        lang_note = "Write entirely in Japanese. Use 第{}章 format when referencing chapter numbers.".format(NUM_KANJI.get(chapter_num, str(chapter_num)))
        chapter_ref = f"第{NUM_KANJI.get(chapter_num, str(chapter_num))}章：{chapter_title}"
    else:
        chapter_ref = f"Chapter {NUM_WORDS.get(chapter_num, str(chapter_num))}: {chapter_title}"
        lang_note = "Write in English."

    context_line  = f"\nPrevious chapters summary: {previous_summary}" if previous_summary else ""
    author_story  = book_details.get("author_story", "")
    main_message  = book_details.get("main_message", "")
    story_line    = f"\nAuthor's real personal story (weave in naturally, do not copy verbatim): {author_story}" if author_story else ""
    message_line  = f"\nCore message of the entire book: {main_message}" if main_message else ""

    prompt = f"""Write a complete book chapter:
{chapter_ref}

Book: {book_details['title']}
Topic: {book_details['topic']}
Audience: {book_details['audience']}
{context_line}
{story_line}
{message_line}

Writing style instructions:
{writing_instructions}

{lang_note}

Rules:
- Target length: {words_target} words
- Structure: opening hook → 3 sections → closing reflection
- NEVER use the word "journey"
- Address reader as "you" at least 3 times
- Include at least one personal story or vulnerable moment
- Vary sentence length: mix short punchy sentences with longer flowing ones
- Do NOT number the sections with headers
- Write only the chapter body text. No chapter title heading at the start."""

    content = None
    for attempt in range(3):
        try:
            response = _call_with_retry(
                client.messages.create,
                model="claude-sonnet-4-6",
                max_tokens=min(words_target * 2, 8000),
                system=f"You are a professional ghostwriter writing in this exact style: {writing_instructions[:500]}",
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.content[0].text.strip()
            if content:
                break
        except Exception as e:
            print(f"⚠️ Chapter {chapter_num} attempt {attempt+1} error: {type(e).__name__}: {e}")
            if attempt < 2:
                print(f"   Retrying in 15s...")
                time.sleep(15)
    if not content:
        raise RuntimeError(f"第{chapter_num}章の生成に3回失敗しました。APIの状態を確認してください。")

    # Generate 2-sentence summary
    try:
        summary_response = _call_with_retry(
            client.messages.create,
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[{"role": "user", "content": f"Summarize this chapter in exactly 2 sentences:\n\n{content[:3000]}"}]
        )
        summary = summary_response.content[0].text.strip()
    except Exception as e:
        summary = f"Chapter {chapter_num} explored {chapter_title}."

    return content, summary


def generate_conclusion(book_details, all_summaries, writing_instructions, client):
    """Write a 500-700 word conclusion that feels like a letter from a trusted friend."""
    language = book_details.get("language", "english")

    if language == "japanese":
        lang_note = "Write entirely in Japanese."
    else:
        lang_note = "Write in English."

    summaries_text = "\n".join(all_summaries) if isinstance(all_summaries, list) else all_summaries

    prompt = f"""Write a book conclusion for:
Title: {book_details['title']}
Topic: {book_details['topic']}
Audience: {book_details['audience']}

What the book covered:
{summaries_text}

Writing style instructions:
{writing_instructions}

{lang_note}

Rules:
- 500–700 words
- Do NOT summarize chapter by chapter
- Feel like a heartfelt letter from a trusted friend
- Acknowledge the reader's courage in reading this far
- End with ONE thing the reader can do or see differently starting today
- Leave the reader with hope, not a checklist

Write only the conclusion text. No heading."""

    try:
        response = _call_with_retry(
            client.messages.create,
            model="claude-sonnet-4-6",
            max_tokens=1200,
            system=f"You are a professional ghostwriter writing in this exact style: {writing_instructions[:500]}",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"⚠️ Conclusion error: {e}")
        return f"Thank you for reading {book_details['title']}."


def generate_kdp_metadata(book_details, client):
    """Generate Amazon KDP metadata: description, keywords, BISAC categories."""
    language = book_details.get("language", "english")

    if language == "japanese":
        lang_note = "Write the description in Japanese. Keywords should be Japanese search terms people actually use on Amazon Japan."
    else:
        lang_note = "Write in English. Keywords should be English search terms people actually use on Amazon."

    prompt = f"""Generate Amazon KDP metadata for this book:
Title: {book_details['title']}
Topic: {book_details['topic']}
Audience: {book_details['audience']}
{lang_note}

Return ONLY a valid JSON object:
{{
  "kdp_description": "<400-word Amazon book description starting with a compelling hook — NOT starting with the title>",
  "kdp_keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5", "keyword6", "keyword7"],
  "bisac_primary": "<BISAC code — description, e.g. SEL016000 — Self-Help / Personal Growth / General>",
  "bisac_secondary": "<second BISAC code — description>"
}}

Rules:
- Description must be exactly 7 keywords
- Keywords must be phrases people ACTUALLY search on Amazon, not generic words
- BISAC codes must be real valid codes

Return ONLY the JSON. No markdown."""

    safe_default = {
        "kdp_description": f"Discover the transformative power of {book_details['topic']}. This book offers practical wisdom and heartfelt guidance for {book_details['audience']}. Through real stories and actionable insights, you'll find the tools you need to create meaningful change in your life.",
        "kdp_keywords": [book_details["topic"], "self help", "personal development", "life change", "motivation", "mindset", "transformation"],
        "bisac_primary": "SEL016000 — Self-Help / Personal Growth / General",
        "bisac_secondary": "SEL031000 — Self-Help / Personal Growth / Happiness"
    }

    for attempt in range(2):
        try:
            response = _call_with_retry(
                client.messages.create,
                model="claude-sonnet-4-6",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response.content[0].text.strip()
            raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            return json.loads(raw)
        except json.JSONDecodeError:
            if attempt == 0:
                print("⚠️ KDP metadata JSON parse failed, retrying...")
            else:
                return safe_default
        except Exception as e:
            print(f"⚠️ KDP metadata error: {e}")
            return safe_default

    return safe_default


def generate_full_book(book_details, author_name):
    """Main function: orchestrate full book generation."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    print(f"\n📚 Starting book generation: {book_details['title']}")
    print(f"👤 Author profile: {author_name}")

    # Load style profile
    style_profile, writing_instructions = load_profile(author_name)
    if style_profile is None:
        raise ValueError(
            f"著者プロフィール '{author_name}' が見つかりません。"
            "先にSTEP 1で文章サンプルを解析してください。"
        )

    # Attach language from profile if not set in book_details
    if "language" not in book_details or not book_details["language"]:
        book_details["language"] = style_profile.get("language", "english")

    num_chapters = int(book_details.get("chapters", 5))
    # Keep safe filename ASCII-safe for file system
    import unicodedata
    safe_filename = book_details["title"].replace(" ", "_")
    safe_filename = "".join(
        c if c.isascii() and (c.isalnum() or c in "_-") else "_"
        for c in safe_filename
    ).strip("_") or "book"
    draft_path = OUTPUT_DIR / f"{safe_filename}_draft.json"

    # Quick API credit check before starting
    print("[5%] 🔑 APIクレジットを確認中...")
    try:
        test_resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=5,
            messages=[{"role": "user", "content": "hi"}]
        )
    except Exception as credit_err:
        err_str = str(credit_err)
        if "credit balance" in err_str or "balance is too low" in err_str:
            raise ValueError(
                "❌ APIクレジットが不足しています。\n"
                "Claude Console (console.anthropic.com) → Billing → Buy credits で"
                "クレジットを追加してから再試行してください。"
            )
        # Other errors (network etc.) — continue anyway

    # Generate outline
    print("[5%] 📋 Generating outline...")
    outline = generate_outline(book_details, writing_instructions, client)
    chapter_titles = outline.get("chapter_titles", [f"Chapter {i+1}" for i in range(num_chapters)])

    # Ensure correct number of chapters
    while len(chapter_titles) < num_chapters:
        chapter_titles.append(f"Chapter {len(chapter_titles)+1}")
    chapter_titles = chapter_titles[:num_chapters]

    # Generate introduction
    print("[10%] ✍️  Writing introduction...")
    introduction = generate_introduction(book_details, outline, writing_instructions, client)

    # Generate chapters
    chapters = []
    all_summaries = []
    previous_summary = ""

    for i, title in enumerate(chapter_titles):
        chapter_num = i + 1
        pct = int(10 + (i / num_chapters) * 60)
        print(f"[{pct}%] ✅ Writing Chapter {chapter_num} of {num_chapters}: {title}")

        content, summary = generate_chapter(
            chapter_num, title, book_details,
            previous_summary, writing_instructions, client
        )

        chapters.append({
            "number": chapter_num,
            "title": title,
            "content": content,
            "summary": summary
        })
        all_summaries.append(summary)
        previous_summary = " ".join(all_summaries[-3:])  # rolling 3-chapter context

        # Save draft after each chapter (crash protection)
        draft = {
            "title": book_details["title"],
            "outline": outline,
            "introduction": introduction,
            "chapters": chapters
        }
        with open(draft_path, "w", encoding="utf-8") as f:
            json.dump(draft, f, ensure_ascii=False, indent=2)

    # Generate conclusion
    print("[75%] ✍️  Writing conclusion...")
    conclusion = generate_conclusion(book_details, all_summaries, writing_instructions, client)

    # Generate KDP metadata
    print("[85%] 📊 Generating KDP metadata...")
    kdp_meta = generate_kdp_metadata(book_details, client)

    # Calculate stats — use character count for Japanese, word count for English
    all_text = introduction + " " + " ".join(c["content"] for c in chapters) + " " + conclusion
    language = book_details.get("language", "english")
    if language == "japanese":
        # Japanese: ~500 characters per page, ~2 chars per "word" equivalent
        total_words = len(all_text.replace(" ", "").replace("\n", ""))
        estimated_pages = round(total_words / 500)
    else:
        total_words = len(all_text.split())
        estimated_pages = round(total_words / 250)

    book_data = {
        "title": book_details["title"],
        "subtitle": outline.get("subtitle", ""),
        "author_display_name": book_details.get("author_display_name", author_name),
        "introduction": introduction,
        "chapters": chapters,
        "conclusion": conclusion,
        "kdp_description": kdp_meta.get("kdp_description", ""),
        "kdp_keywords": kdp_meta.get("kdp_keywords", []),
        "bisac_primary": kdp_meta.get("bisac_primary", ""),
        "bisac_secondary": kdp_meta.get("bisac_secondary", ""),
        "total_words": total_words,
        "estimated_pages": estimated_pages,
        "language": book_details.get("language", "english")
    }

    # Save final JSON
    final_path = OUTPUT_DIR / f"{safe_filename}_final.json"
    with open(final_path, "w", encoding="utf-8") as f:
        json.dump(book_data, f, ensure_ascii=False, indent=2)

    print(f"[95%] 💾 Book data saved: {final_path}")
    print(f"📖 Total words: {total_words:,} | Estimated pages: {estimated_pages}")

    # Attach the actual saved path so build_book.py can reference it correctly
    book_data["_final_json_path"] = str(final_path)
    return book_data
