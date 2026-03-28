"""Run this to start the Kindle Book Machine."""
import subprocess
import sys
import os
import webbrowser
import threading
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Always run from the folder where START.py lives
os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("""
╔══════════════════════════════════════╗
║   📚  KINDLE BOOK MACHINE            ║
║   Starting up...                     ║
╚══════════════════════════════════════╝
""")

# Check .env exists
if not os.path.exists(".env"):
    print("❌ Missing .env file. Create it with your ANTHROPIC_API_KEY.")
    sys.exit(1)

# Check API key is set
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key == "REPLACE_WITH_YOUR_KEY_HERE":
        print("❌ ANTHROPIC_API_KEY is not set in your .env file.")
        print("   Open .env and replace REPLACE_WITH_YOUR_KEY_HERE with your real key.")
        sys.exit(1)
except ImportError:
    print("❌ python-dotenv not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

# Create missing folders
for folder in ["uploads", "output", "profiles", "templates", "static", "styles"]:
    os.makedirs(folder, exist_ok=True)

print("✅ All folders ready")
print("✅ API key found")
print("🌐 Starting server at http://localhost:5000")
print("📖 Opening browser in 3 seconds...")
print("\nTo stop: press Ctrl+C\n")


def open_browser():
    time.sleep(3)
    webbrowser.open("http://localhost:5000")


threading.Thread(target=open_browser, daemon=True).start()
subprocess.run([sys.executable, "app.py"])
