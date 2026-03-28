"""
スマホからアクセスできるURLを作成します。
このファイルを実行するだけでOK！
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import os, threading, time, subprocess
from pathlib import Path

# Always load .env from same folder as this script
_HERE = Path(__file__).parent.resolve()
os.chdir(_HERE)  # Make sure cwd is the app folder

from dotenv import load_dotenv
load_dotenv(_HERE / ".env", override=True)

print("""
╔══════════════════════════════════════════╗
║   📚  KINDLE BOOK MACHINE               ║
║   📱  スマホアクセス版                   ║
╚══════════════════════════════════════════╝
""")

# フォルダ確認
for folder in ['uploads', 'output', 'profiles', 'templates', 'static', 'styles']:
    Path(folder).mkdir(exist_ok=True)

# .env確認
if not os.path.exists('.env'):
    print("❌ .envファイルが見つかりません。ANTHROPIC_API_KEYを設定してください。")
    sys.exit(1)

api_key = os.getenv("ANTHROPIC_API_KEY", "")
if not api_key or api_key == "REPLACE_WITH_YOUR_KEY":
    print("❌ ANTHROPIC_API_KEYが設定されていません。.envファイルを確認してください。")
    sys.exit(1)

print("✅ APIキー確認済み")

# ngrokトークン確認
ngrok_token = os.getenv("NGROK_AUTH_TOKEN", "")

import socket, webbrowser

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

local_ip = get_local_ip()
local_url = f"http://{local_ip}:5000"

# Flaskをバックグラウンドで起動
print("🌐 サーバーを起動中...")
flask_process = subprocess.Popen(
    [sys.executable, "app.py"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)
time.sleep(3)

# ngrokで公開URLを試みる
public_url = None
if ngrok_token:
    try:
        from pyngrok import ngrok, conf
        conf.get_default().auth_token = ngrok_token
        tunnel = ngrok.connect(5000, "http")
        public_url = tunnel.public_url
        print("✅ 公開URL作成成功！")
    except Exception as e:
        print(f"⚠️ ngrok失敗: {e}")

# 結果を表示
if public_url:
    print(f"""
╔══════════════════════════════════════════════════╗
║   ✅  完成！どこからでもアクセスできます          ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║   🌍 公開URL（外出先でも使える）:                 ║
║   {public_url:<48} ║
║                                                  ║
║   📱 同じWiFiのスマホ:                           ║
║   {local_url:<48} ║
║                                                  ║
║   💻 このPC:  http://localhost:5000              ║
║                                                  ║
╚══════════════════════════════════════════════════╝
""")
    webbrowser.open(public_url)
else:
    print(f"""
╔══════════════════════════════════════════════════╗
║   ✅  完成！同じWiFiのスマホで使えます            ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║   📱 スマホのブラウザで開く（同じWiFi必須）:      ║
║                                                  ║
║      {local_url:<44} ║
║                                                  ║
║   💻 このPC:  http://localhost:5000              ║
║                                                  ║
╠══════════════════════════════════════════════════╣
║  💡 外出先でも使いたい場合:                       ║
║     1. https://ngrok.com で無料登録              ║
║     2. トークンを .env に追加:                   ║
║        NGROK_AUTH_TOKEN=あなたのトークン          ║
║     3. このファイルを再実行                       ║
╚══════════════════════════════════════════════════╝
""")
    webbrowser.open(f"http://localhost:5000")

print("🟢 実行中... (Ctrl+C で停止)\n")
try:
    flask_process.wait()
except KeyboardInterrupt:
    print("\n👋 停止しました。")
    flask_process.terminate()
