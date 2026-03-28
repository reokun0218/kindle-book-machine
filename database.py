# database.py — user accounts, subscriptions, usage tracking
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import sqlite3
from pathlib import Path
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = Path("data/app.db")

# ── Plan limits ────────────────────────────────────────────────────────────
PLANS = {
    "free": {
        "name": "無料プラン",
        "name_en": "Free",
        "price_monthly": 0,
        "books_per_month": 999,
        "max_chapters": 999,
        "epub_download": True,
        "kdp_download": True,
        "badge": "FREE",
    },
    "starter": {
        "name": "スタータープラン",
        "name_en": "Starter",
        "price_monthly": 980,        # ¥980/month
        "books_per_month": 5,
        "max_chapters": 999,
        "epub_download": True,
        "kdp_download": True,
        "badge": "STARTER",
    },
    "pro": {
        "name": "プロプラン",
        "name_en": "Pro",
        "price_monthly": 2980,       # ¥2,980/month
        "books_per_month": 999,      # unlimited
        "max_chapters": 999,
        "epub_download": True,
        "kdp_download": True,
        "badge": "PRO",
    },
}


def get_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT DEFAULT '',
            plan TEXT DEFAULT 'free',
            stripe_customer_id TEXT DEFAULT '',
            stripe_subscription_id TEXT DEFAULT '',
            books_this_month INTEGER DEFAULT 0,
            month_key TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT DEFAULT '',
            author_name TEXT DEFAULT '',
            status TEXT DEFAULT 'preview',
            epub_path TEXT DEFAULT '',
            kdp_path TEXT DEFAULT '',
            json_path TEXT DEFAULT '',
            word_count INTEGER DEFAULT 0,
            chapter_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """)
    print("✅ Database initialized")


# ── User CRUD ──────────────────────────────────────────────────────────────

def create_user(email, password, name=""):
    """Create a new user. Returns user dict or raises ValueError."""
    pw_hash = generate_password_hash(password)
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)",
                (email.lower().strip(), pw_hash, name.strip())
            )
        return get_user_by_email(email)
    except sqlite3.IntegrityError:
        raise ValueError("このメールアドレスはすでに登録されています。")


def get_user_by_email(email):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


def verify_password(email, password):
    """Returns user dict if valid, None otherwise."""
    user = get_user_by_email(email)
    if not user:
        return None
    if check_password_hash(user["password_hash"], password):
        return user
    return None


def update_user_plan(user_id, plan, stripe_customer_id="", stripe_subscription_id=""):
    with get_db() as conn:
        conn.execute(
            """UPDATE users SET plan=?, stripe_customer_id=?, stripe_subscription_id=?
               WHERE id=?""",
            (plan, stripe_customer_id, stripe_subscription_id, user_id)
        )


# ── Usage tracking ─────────────────────────────────────────────────────────

def _current_month_key():
    return datetime.now().strftime("%Y-%m")


def get_books_used_this_month(user_id):
    """Returns how many books user has generated this month."""
    user = get_user_by_id(user_id)
    if not user:
        return 0
    month_key = _current_month_key()
    if user["month_key"] != month_key:
        # New month — reset counter
        with get_db() as conn:
            conn.execute(
                "UPDATE users SET books_this_month=0, month_key=? WHERE id=?",
                (month_key, user_id)
            )
        return 0
    return user["books_this_month"]


def increment_book_usage(user_id):
    month_key = _current_month_key()
    with get_db() as conn:
        conn.execute(
            """UPDATE users SET
               books_this_month = CASE WHEN month_key=? THEN books_this_month+1 ELSE 1 END,
               month_key = ?
               WHERE id=?""",
            (month_key, month_key, user_id)
        )


def can_generate_book(user_id):
    """Returns (allowed: bool, reason: str)."""
    user = get_user_by_id(user_id)
    if not user:
        return False, "ログインが必要です。"
    plan = PLANS.get(user["plan"], PLANS["free"])
    used = get_books_used_this_month(user_id)
    limit = plan["books_per_month"]
    if used >= limit:
        if user["plan"] == "free":
            return False, f"無料プランの今月の上限（{limit}冊）に達しました。アップグレードして続けましょう。"
        else:
            return False, f"今月の上限（{limit}冊）に達しました。来月またお試しください。"
    return True, ""


def get_plan_limits(user_id):
    """Returns plan limits dict for this user."""
    user = get_user_by_id(user_id)
    if not user:
        return PLANS["free"]
    return PLANS.get(user["plan"], PLANS["free"])


# ── Book records ───────────────────────────────────────────────────────────

def save_book_record(user_id, title, author_name, status,
                     epub_path="", kdp_path="", json_path="",
                     word_count=0, chapter_count=0):
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO books
               (user_id, title, author_name, status, epub_path, kdp_path,
                json_path, word_count, chapter_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, title, author_name, status, epub_path, kdp_path,
             json_path, word_count, chapter_count)
        )
        return cursor.lastrowid


def get_user_books(user_id):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM books WHERE user_id=? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Init on import ─────────────────────────────────────────────────────────
init_db()
