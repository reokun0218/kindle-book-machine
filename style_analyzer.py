# style_analyzer.py — reads writing samples, extracts author style
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
import anthropic
from bs4 import BeautifulSoup

load_dotenv(override=True)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

PROFILES_DIR = Path("profiles")


def load_writing_samples(file_paths):
    """Read .txt, .md, .html files and combine into one text string."""
    texts = []
    for path in file_paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
            if str(path).endswith(".html"):
                soup = BeautifulSoup(raw, "lxml")
                text = soup.get_text(separator="\n")
            else:
                text = raw
            texts.append(text.strip())
        except Exception as e:
            print(f"⚠️ Could not read {path}: {e}")

    combined = "\n\n".join(texts)
    word_count = len(combined.split())
    print(f"📄 Loaded {len(file_paths)} file(s) — {word_count} words total")

    if word_count < 200:
        print("⚠️ Small sample — provide 500+ words for best results")

    return combined


def analyze_style_with_claude(text):
    """Send text to Claude and extract style profile as JSON dict."""
    truncated = text[:8000]

    prompt = """Analyze the writing sample below and return ONLY a valid JSON object with these exact keys:

{
  "sentence_length": "short" or "medium" or "long",
  "avg_sentence_words": <number>,
  "vocabulary_level": "simple" or "moderate" or "advanced",
  "tone_adjectives": ["adj1", "adj2", "adj3", "adj4"],
  "uses_metaphors": true or false,
  "metaphor_style": "<15-word description>",
  "uses_personal_stories": true or false,
  "uses_questions": true or false,
  "paragraph_length": "very short" or "short" or "medium" or "long",
  "formality": "very casual" or "casual" or "semi-formal" or "formal",
  "emotional_style": "<one sentence>",
  "writing_rhythm": "<one sentence>",
  "unique_phrases": ["phrase1", "phrase2", "phrase3", "phrase4", "phrase5"],
  "opening_style": "<one sentence>",
  "closing_style": "<one sentence>",
  "talks_to_reader": true or false,
  "language": "english" or "japanese" or "mixed",
  "keigo_level": "n/a" or "casual" or "polite" or "formal" or "very formal",
  "cultural_patterns": "<20-word description>"
}

Return ONLY the JSON object. No explanation. No markdown. No code block.

Writing sample:
""" + truncated

    def call_api():
        return client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system="You are a world-class literary analyst and ghostwriter. Analyze writing samples and extract the author's unique voice with extreme precision.",
            messages=[{"role": "user", "content": prompt}]
        )

    safe_defaults = {
        "sentence_length": "medium",
        "avg_sentence_words": 15,
        "vocabulary_level": "moderate",
        "tone_adjectives": ["clear", "direct", "engaging", "thoughtful"],
        "uses_metaphors": False,
        "metaphor_style": "Minimal use of figurative language",
        "uses_personal_stories": False,
        "uses_questions": False,
        "paragraph_length": "medium",
        "formality": "semi-formal",
        "emotional_style": "Measured and composed tone throughout.",
        "writing_rhythm": "Steady, even pacing with consistent sentence flow.",
        "unique_phrases": ["in other words", "as a result", "for example", "in fact", "at the same time"],
        "opening_style": "Opens with a direct statement or observation.",
        "closing_style": "Closes with a summary or call to reflection.",
        "talks_to_reader": False,
        "language": "english",
        "keigo_level": "n/a",
        "cultural_patterns": "Standard Western narrative structure with linear progression."
    }

    for attempt in range(2):
        try:
            response = call_api()
            raw = response.content[0].text.strip()
            # Strip markdown code block if present
            raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            profile = json.loads(raw)
            return profile
        except json.JSONDecodeError:
            if attempt == 0:
                print("⚠️ JSON parse failed, retrying...")
                continue
            else:
                print("⚠️ JSON parse failed twice — using safe defaults")
                return safe_defaults
        except Exception as e:
            print(f"⚠️ API error: {e}")
            return safe_defaults

    return safe_defaults


def create_writing_instructions(style_profile):
    """Convert style profile dict into one paragraph of writing instructions."""
    p = style_profile

    tone = ", ".join(p.get("tone_adjectives", ["clear", "engaging"]))
    avg_words = p.get("avg_sentence_words", 15)
    para_len = p.get("paragraph_length", "medium")
    formality = p.get("formality", "semi-formal")
    vocab = p.get("vocabulary_level", "moderate")
    emotional = p.get("emotional_style", "")
    rhythm = p.get("writing_rhythm", "")

    metaphor_line = ""
    if p.get("uses_metaphors"):
        metaphor_line = f" Use metaphors and figurative language: {p.get('metaphor_style', '')}."

    story_line = " Include personal stories and vulnerable moments." if p.get("uses_personal_stories") else ""
    question_line = " Engage the reader with rhetorical questions." if p.get("uses_questions") else ""
    reader_line = " Address the reader directly as 'you' throughout." if p.get("talks_to_reader") else ""

    unique = p.get("unique_phrases", [])
    phrase_line = ""
    if unique:
        phrase_line = f" Occasionally use characteristic phrases like: {', '.join(unique[:3])}."

    keigo = p.get("keigo_level", "n/a")
    cultural = p.get("cultural_patterns", "")
    lang = p.get("language", "english")

    japanese_line = ""
    if lang in ("japanese", "mixed"):
        keigo_desc = {"casual": "タメ口 (casual speech)", "polite": "丁寧語 (polite speech)", "formal": "敬語 (formal speech)", "very formal": "非常に丁寧な敬語 (very formal speech)"}.get(keigo, "standard polite Japanese")
        japanese_line = f" Write in Japanese using {keigo_desc}. {cultural}"

    instructions = (
        f"Write in a {tone} tone. "
        f"Use {p.get('sentence_length', 'medium')}-length sentences averaging {avg_words} words. "
        f"Keep paragraphs {para_len} (following the author's natural rhythm). "
        f"Maintain a {formality} register with {vocab} vocabulary. "
        f"{emotional} {rhythm}"
        f"{metaphor_line}{story_line}{question_line}{reader_line}"
        f" Opening style: {p.get('opening_style', 'Start with a direct statement.')}."
        f" Closing style: {p.get('closing_style', 'End with a reflection.')}."
        f"{phrase_line}"
        f"{japanese_line}"
    )

    return instructions.strip()


def generate_style_preview(style_profile):
    """Call Claude to write one paragraph in the author's style."""
    instructions = create_writing_instructions(style_profile)
    lang = style_profile.get("language", "english")

    if lang == "japanese":
        topic = "成長とは、今いる場所を受け入れることから始まると気づいた瞬間"
    else:
        topic = "the moment I realized that growth begins with accepting where you are"

    prompt = f"""Write ONE paragraph about: "{topic}"

Writing style instructions:
{instructions}

Write only the paragraph. No title. No explanation."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            system="You are a professional ghostwriter. Write exactly in the style described.",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"⚠️ Preview generation error: {e}")
        return "Preview unavailable."


def save_profile(style_profile, author_name, writing_instructions):
    """Save style profile and writing instructions to profiles/ folder."""
    PROFILES_DIR.mkdir(exist_ok=True)
    path = PROFILES_DIR / f"{author_name}_profile.json"
    data = {
        "author_name": author_name,
        "style_profile": style_profile,
        "writing_instructions": writing_instructions
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ Profile saved: profiles/{author_name}_profile.json")


def load_profile(author_name):
    """Load a saved author profile. Returns (style_profile, writing_instructions) or (None, None)."""
    path = PROFILES_DIR / f"{author_name}_profile.json"
    if not path.exists():
        print(f"⚠️ Profile not found: {path}")
        return None, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["style_profile"], data["writing_instructions"]
    except Exception as e:
        print(f"⚠️ Error loading profile: {e}")
        return None, None


def list_saved_profiles():
    """Return list of saved author names."""
    if not PROFILES_DIR.exists():
        return []
    files = PROFILES_DIR.glob("*_profile.json")
    return [f.stem.replace("_profile", "") for f in files]


def analyze_author(file_paths, author_name):
    """Main function: analyze writing samples and build a complete style profile."""
    print(f"\n🔍 Analyzing writing style for: {author_name}")

    print("📂 Step 1/4 — Loading writing samples...")
    text = load_writing_samples(file_paths)

    print("🧠 Step 2/4 — Analyzing style with Claude...")
    style_profile = analyze_style_with_claude(text)

    print("📝 Step 3/4 — Creating writing instructions...")
    writing_instructions = create_writing_instructions(style_profile)

    print("✍️  Step 4/4 — Generating style preview...")
    preview_paragraph = generate_style_preview(style_profile)

    save_profile(style_profile, author_name, writing_instructions)

    print("\n✅ Style analysis complete!")
    return style_profile, writing_instructions, preview_paragraph


# ── Test ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os

    os.makedirs("uploads", exist_ok=True)
    sample_text = """There's a particular kind of exhaustion that comes not from doing too much, but from pretending too long.
I remember the morning I sat in my car in the parking lot of a job I no longer recognized as mine, staring at the dashboard clock,
watching the minutes tick by without moving. Something in me had gone quiet in a way that scared me.

It wasn't burnout in the way people talk about it — the dramatic collapse, the breakdown, the obvious sign.
It was subtler than that. It was the slow erasure of the self that happens when you keep saying yes to everyone but yourself.
I had become very good at performing okayness.

What I've come to understand, through years of working with people in transition, is that most of us don't arrive at change through inspiration.
We arrive through exhaustion. We change because we finally get tired enough of who we've been pretending to be.

And here's what nobody tells you about that moment: it's not a failure. It's an invitation.
Your body, your heart, your whole tired system is saying — there's something truer available to you. Are you ready to look for it?

The path forward is rarely straight. It's rarely logical. Sometimes it starts with admitting you're lost.
Sometimes it starts with sitting still long enough to hear what you actually want. Sometimes it starts with a single honest conversation
with the person in the mirror you've been avoiding for years.

I don't believe in quick fixes. I believe in small, honest steps. I believe in the courage it takes to say:
this is where I am, and I'm willing to begin from here.

That's not weakness. That's the bravest thing a person can do."""

    with open("uploads/test_sample.txt", "w", encoding="utf-8") as f:
        f.write(sample_text)

    style_profile, writing_instructions, preview = analyze_author(
        ["uploads/test_sample.txt"], "Test_Author"
    )

    print("\n── Style Profile ──────────────────────────────────────")
    print(json.dumps(style_profile, ensure_ascii=False, indent=2))
    print("\n── Writing Instructions ───────────────────────────────")
    print(writing_instructions)
    print("\n── Style Preview ──────────────────────────────────────")
    print(preview)
