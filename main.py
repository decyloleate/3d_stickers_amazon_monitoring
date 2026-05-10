import time
import os
import requests
import threading
from playwright.sync_api import sync_playwright
from flask import Flask

app = Flask(__name__)

discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

def send_debug_info(message, image_path=None):
    """Discordにテキストと画像を送信する"""
    if not discord_webhook_url: return
    try:
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as f:
                requests.post(discord_webhook_url, data={"content": message}, files={"file": f})
        else:
            requests.post(discord_webhook_url, json={"content": message})
    except Exception as e:
        print(f"Discord送信エラー: {e}")

def debug_amazon():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="ja-JP"
        )
        page = context.new_page()
        
        # ※今回は画面を撮影するため、画像のブロック設定は外しています

        print("デバッグ調査開始: ロレッタのページを開きます")
        try:
            page.goto("https://amzn.asia/d/04Hjs6ii", wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(5000) # ページが完全に描画されるのを待つ
            
            # 1. 証拠写真を撮影
            screenshot_path = "debug_screenshot.png"
            page.screenshot(path=screenshot_path)
            
            # 2. 右側のカート・価格エリアの生のHTMLテキストを抽出
            buybox_text = "取得不可（要素が見つかりません）"
            # 定期おトク便や通常購入の枠を広めに取得
            buybox = page.locator("#desktop_buybox, #rightCol, #buyBoxAccordion").first
            if buybox.is_visible():
                buybox_text = buybox.inner_text()
                
            # Renderのログに出力
            print("\n================ 取得した生テキスト ================")
            print(buybox_text)
            print("====================================================\n")
            
            # Discordに画像を送信
            send_debug_info("**【デバッグ調査】** 現在、プログラムにはこのように見えています。Renderのログに生テキストを出力しました。", screenshot_path)
            print("Discordに画面キャプチャを送信しました。")

        except Exception as e:
            print(f"デバッグ中にエラー発生: {e}")
        
        # 調査用なので1回実行したら待機させる
        while True:
            time.sleep(60)

@app.route("/")
def health_check():
    return "Debug Mode Running"

if __name__ == "__main__":
    threading.Thread(target=debug_amazon, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
