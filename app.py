# app.py — Flask web server with auth + subscription gating
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import os
import json
import threading
from pathlib import Path
from flask import (Flask, render_template, request, jsonify,
                   send_file, session, redirect, url_for)
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "kindle_secret_2024")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB

UPLOAD_FOLDER = Path("uploads")
OUTPUT_FOLDER = Path("output")
ALLOWED_EXTENSIONS = {"txt", "md", "html"}

# Per-user generation status (keyed by user_id)
generation_status = {}   # {user_id: {...}}

STRIPE_SECRET    = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUB       = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK   = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_STARTER   = os.getenv("STRIPE_STARTER_PRICE_ID", "")
STRIPE_PRO       = os.getenv("STRIPE_PRO_PRICE_ID", "")

if STRIPE_SECRET:
    import stripe
    stripe.api_key = STRIPE_SECRET


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    from database import get_user_by_id
    return get_user_by_id(uid)


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def get_status(user_id):
    return generation_status.get(user_id, {
        "running": False, "progress": 0,
        "message": "準備完了", "error": None,
        "output_files": {}, "is_preview": False
    })


def set_status(user_id, **kwargs):
    if user_id not in generation_status:
        generation_status[user_id] = {
            "running": False, "progress": 0,
            "message": "準備完了", "error": None,
            "output_files": {}, "is_preview": False
        }
    generation_status[user_id].update(kwargs)


# ══════════════════════════════════════════════════════════════════════════
# AUTH ROUTES
# ══════════════════════════════════════════════════════════════════════════

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))
    if request.method == "GET":
        return render_template("login.html", mode="login")

    data = request.get_json(force=True, silent=True) or {}
    email    = data.get("email", "").strip()
    password = data.get("password", "")

    from database import verify_password
    user = verify_password(email, password)
    if not user:
        return jsonify({"success": False, "error": "メールアドレスまたはパスワードが間違っています。"})

    session["user_id"] = user["id"]
    return jsonify({"success": True})


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(force=True, silent=True) or {}
    email    = data.get("email", "").strip()
    password = data.get("password", "")
    name     = data.get("name", "").strip()

    if not email or not password:
        return jsonify({"success": False, "error": "メールアドレスとパスワードを入力してください。"})
    if len(password) < 6:
        return jsonify({"success": False, "error": "パスワードは6文字以上で設定してください。"})

    try:
        from database import create_user
        user = create_user(email, password, name)
        session["user_id"] = user["id"]
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ══════════════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════

@app.route("/")
@login_required
def index():
    from style_analyzer import list_saved_profiles
    from database import get_user_by_id, get_books_used_this_month, PLANS, get_user_books
    user = get_user_by_id(session["user_id"])
    plan_info = PLANS.get(user["plan"], PLANS["free"])
    books_used = get_books_used_this_month(user["id"])
    recent_books = get_user_books(user["id"])[:5]
    return render_template(
        "index.html",
        saved_profiles=list_saved_profiles(),
        user=user,
        plan=plan_info,
        books_used=books_used,
        recent_books=recent_books,
        stripe_pub=STRIPE_PUB,
    )


@app.route("/analyze-style", methods=["POST"])
@login_required
def analyze_style():
    try:
        author_name = request.form.get("author_name", "").strip()
        if not author_name:
            return jsonify({"success": False, "error": "プロフィール名を入力してください。"})

        files = request.files.getlist("samples")
        if not files or all(f.filename == "" for f in files):
            return jsonify({"success": False, "error": "文章サンプルをアップロードしてください。"})

        UPLOAD_FOLDER.mkdir(exist_ok=True)
        saved_paths = []
        for f in files:
            if f and f.filename and allowed_file(f.filename):
                filename = secure_filename(f.filename)
                path = UPLOAD_FOLDER / filename
                f.save(str(path))
                saved_paths.append(str(path))

        if not saved_paths:
            return jsonify({"success": False, "error": "有効なファイルがありません（.txt / .md / .html のみ対応）。"})

        from style_analyzer import analyze_author
        style_profile, writing_instructions, preview_paragraph = analyze_author(saved_paths, author_name)
        return jsonify({
            "success": True,
            "author_name": author_name,
            "preview_paragraph": preview_paragraph,
            "message": f"文体解析完了！プロフィール「{author_name}」を保存しました。"
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/generate-book", methods=["POST"])
@login_required
def generate_book():
    from database import can_generate_book, get_plan_limits, PLANS, get_user_by_id

    user_id = session["user_id"]
    user    = get_user_by_id(user_id)
    status  = get_status(user_id)

    if status.get("running"):
        return jsonify({"success": False, "error": "生成中です。しばらくお待ちください。"})

    # Check usage limits
    allowed, reason = can_generate_book(user_id)
    if not allowed:
        return jsonify({"success": False, "error": reason, "upgrade_required": True})

    try:
        data = request.get_json(force=True, silent=True) or {}
        plan_limits = get_plan_limits(user_id)
        is_free = user["plan"] == "free"

        # On free plan, cap chapters at plan limit
        requested_chapters = int(data.get("chapters", 5))
        actual_chapters = min(requested_chapters, plan_limits["max_chapters"]) if is_free else requested_chapters

        book_details = {
            "title":              data.get("title", "").strip(),
            "topic":              data.get("topic", "").strip(),
            "audience":           data.get("audience", "").strip(),
            "chapters":           actual_chapters,
            "words_per_chapter":  int(data.get("words_per_chapter", 1500)),
            "language":           data.get("language", "japanese"),
            "author_display_name": data.get("author_display_name", "").strip(),
            "requested_chapters": requested_chapters,
            # Personalization
            "author_story":       data.get("author_story", "").strip(),
            "main_message":       data.get("main_message", "").strip(),
            # Upsell / bonus (all optional)
            "bonus_title":        data.get("bonus_title", "").strip(),
            "bonus_description":  data.get("bonus_description", "").strip(),
            "line_url":           data.get("line_url", "").strip(),
            "consultation_url":   data.get("consultation_url", "").strip(),
            "upsell_product":     data.get("upsell_product", "").strip(),
            "lead_magnet":        data.get("lead_magnet", "").strip(),
        }
        author_name = data.get("author_name", "").strip()

        if not book_details["title"]:
            return jsonify({"success": False, "error": "タイトルを入力してください。"})
        if not author_name:
            return jsonify({"success": False, "error": "先にSTEP 1で文体を解析してください。"})

        set_status(user_id,
                   running=True, progress=0,
                   message="準備中...", error=None,
                   output_files={},
                   is_preview=is_free,
                   requested_chapters=requested_chapters,
                   actual_chapters=actual_chapters)

        thread = threading.Thread(
            target=run_generation,
            args=(book_details, author_name, user_id)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            "success": True,
            "is_preview": is_free,
            "preview_chapters": actual_chapters,
            "total_chapters": requested_chapters,
        })

    except Exception as e:
        set_status(user_id, running=False)
        return jsonify({"success": False, "error": str(e)})


@app.route("/status")
@login_required
def status():
    return jsonify(get_status(session["user_id"]))


@app.route("/reset-status", methods=["POST"])
@login_required
def reset_status():
    user_id = session["user_id"]
    generation_status.pop(user_id, None)
    return jsonify({"success": True})


@app.route("/download/<file_type>")
@login_required
def download(file_type):
    user_id = session["user_id"]

    # Try in-memory status first
    paths = get_status(user_id).get("output_files", {})
    if file_type == "docx":
        path = paths.get("docx_path")
        pattern = "*.docx"
    elif file_type == "kdp_sheet":
        path = paths.get("kdp_sheet_path")
        pattern = "*_KDP_SHEET.txt"
    else:
        return jsonify({"error": "不明なファイルタイプ"}), 404

    # Fallback: scan output folder for most recent matching file
    if not path or not Path(path).exists():
        candidates = sorted(
            OUTPUT_FOLDER.glob(pattern),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )
        if candidates:
            path = str(candidates[0])

    if not path or not Path(path).exists():
        return jsonify({"error": "ファイルが見つかりません。先に本を生成してください。"}), 404

    return send_file(path, as_attachment=True)


@app.route("/list-profiles")
@login_required
def list_profiles():
    from style_analyzer import list_saved_profiles
    return jsonify({"profiles": list_saved_profiles()})


@app.route("/preview")
@login_required
def preview():
    try:
        user_id = session["user_id"]
        files = get_status(user_id).get("output_files", {})
        json_path = files.get("json_path")
        if not json_path or not Path(json_path).exists():
            return jsonify({"success": False, "error": "データが見つかりません。"})

        with open(json_path, "r", encoding="utf-8") as f:
            book_data = json.load(f)

        chapters = book_data.get("chapters", [])
        return jsonify({
            "success": True,
            "chapter_preview": chapters[0].get("content", "")[:500] if chapters else "",
            "stats": {
                "total_words":     book_data.get("total_words", 0),
                "estimated_pages": book_data.get("estimated_pages", 0),
                "chapter_count":   len(chapters),
                "title":           book_data.get("title", ""),
                "subtitle":        book_data.get("subtitle", ""),
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ══════════════════════════════════════════════════════════════════════════
# STRIPE ROUTES
# ══════════════════════════════════════════════════════════════════════════

@app.route("/upgrade/<plan_name>")
@login_required
def upgrade(plan_name):
    if not STRIPE_SECRET:
        return jsonify({"error": "Stripe未設定。.envにSTRIPE_SECRET_KEYを追加してください。"}), 400

    price_map = {"starter": STRIPE_STARTER, "pro": STRIPE_PRO}
    price_id = price_map.get(plan_name)
    if not price_id:
        return jsonify({"error": "無効なプランです。"}), 400

    from database import get_user_by_id
    user = get_user_by_id(session["user_id"])

    try:
        checkout = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            customer_email=user["email"],
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=request.host_url + "upgrade-success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.host_url,
            metadata={"user_id": str(user["id"]), "plan": plan_name}
        )
        return redirect(checkout.url)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/upgrade-success")
@login_required
def upgrade_success():
    if not STRIPE_SECRET:
        return redirect(url_for("index"))
    session_id = request.args.get("session_id")
    if session_id:
        try:
            checkout = stripe.checkout.Session.retrieve(session_id)
            plan = checkout.metadata.get("plan", "starter")
            user_id = int(checkout.metadata.get("user_id", session["user_id"]))
            from database import update_user_plan
            update_user_plan(user_id, plan,
                             stripe_customer_id=checkout.customer or "",
                             stripe_subscription_id=checkout.subscription or "")
        except Exception as e:
            print(f"⚠️ Stripe session error: {e}")
    return redirect(url_for("index"))


@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    if not STRIPE_SECRET:
        return "", 200
    payload    = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK)
    except Exception:
        return "", 400

    if event["type"] == "customer.subscription.deleted":
        sub = event["data"]["object"]
        from database import get_db
        with get_db() as conn:
            conn.execute(
                "UPDATE users SET plan='free' WHERE stripe_subscription_id=?",
                (sub["id"],)
            )
    return "", 200


@app.route("/my-books")
@login_required
def my_books():
    from database import get_user_books, get_user_by_id, PLANS
    user = get_user_by_id(session["user_id"])
    books = get_user_books(user["id"])
    plan_info = PLANS.get(user["plan"], PLANS["free"])
    return render_template("my_books.html", user=user, books=books, plan=plan_info)


# ══════════════════════════════════════════════════════════════════════════
# BACKGROUND GENERATION
# ══════════════════════════════════════════════════════════════════════════

def run_generation(book_details, author_name, user_id):
    from database import increment_book_usage, save_book_record, get_user_by_id, PLANS

    try:
        def update(pct, msg):
            set_status(user_id, progress=pct, message=msg)

        book_details["author_name"] = author_name
        from build_book import complete_book_pipeline
        output_files = complete_book_pipeline(
            book_details, author_name, progress_callback=update
        )

        # Save book record
        user = get_user_by_id(user_id)
        plan = PLANS.get(user["plan"], PLANS["free"])
        is_preview = user["plan"] == "free"
        stats = output_files.get("stats", {})

        save_book_record(
            user_id=user_id,
            title=book_details.get("title", ""),
            author_name=author_name,
            status="preview" if is_preview else "full",
            epub_path="",
            kdp_path=output_files.get("kdp_sheet_path", "") if plan["kdp_download"] else "",
            json_path=output_files.get("json_path", ""),
            word_count=stats.get("total_words", 0),
            chapter_count=stats.get("chapters", 0),
        )
        increment_book_usage(user_id)

        set_status(user_id,
                   running=False, progress=100,
                   message="🎉 本が完成しました！",
                   output_files=output_files)

    except Exception as e:
        set_status(user_id,
                   running=False,
                   error=str(e),
                   message=f"❌ エラー: {str(e)}")


# ══════════════════════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════════════════════

def startup():
    """Create folders and initialise DB — works both locally and on Railway."""
    for folder in ["uploads", "output", "profiles", "data"]:
        Path(folder).mkdir(exist_ok=True)
    from database import init_db
    init_db()

# Always run startup (even when imported by gunicorn / Railway)
startup()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("RAILWAY_ENVIRONMENT") is None
    app.run(host="0.0.0.0", debug=debug, port=port, use_reloader=False)
