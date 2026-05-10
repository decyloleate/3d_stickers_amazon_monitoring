import time
import os
import requests
import threading
import re
from playwright.sync_api import sync_playwright
from flask import Flask

app = Flask(__name__)

# --- 設定項目 ---
target_items = [
    {"name": "ロレッタ", "url": "https://amzn.asia/d/0hZjNvJ3"},
]

price_limit = 99999999999
discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

def send_discord_notify(message):
    if not discord_webhook_url:
        print("【警告】Webhook URLが設定されていません。")
        return
    try:
        response = requests.post(discord_webhook_url, json={"content": message}, timeout=10)
        if response.status_code == 204:
            print("Discord通知を送信しました。")
        else:
            print(f"Discord送信失敗: {response.status_code}")
    except Exception as e:
        print(f"Discord送信エラー: {e}")

def check_amazon_task():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="ja-JP"
        )
        page = context.new_page()
        
        # 画像類をブロックして高速化
        page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())

        print("監視プロセス開始")
        while True:
            for item in target_items:
                try:
                    page.goto(item['url'], wait_until="domcontentloaded", timeout=40000)
                    page.wait_for_timeout(5000)

                    # 1. 価格エリアの特定（より厳密なセレクタに変更）
                    # .a-price-whole は「￥66,000」の「66,000」部分だけを指すクラスです
                    price_element = page.locator(".a-container .a-price-whole").first
                    
                    price = None
                    if price_element.is_visible():
                        raw_text = price_element.inner_text()
                        # 数字以外を削除し、最初に見つかった数値の塊だけを取得
                        digits = re.sub(r'\D', '', raw_text)
                        if digits:
                            price = int(digits)

                    # 2. 販売元の特定（カートボックス内のテキストで判定）
                    buybox = page.locator("#buybox, #desktop_buybox").first
                    is_official = False
                    if buybox.is_visible():
                        bb_text = buybox.inner_text()
                        is_official = any(x in bb_text for x in ["Amazon.co.jp", "Amazonによる発送", "Amazon.co.jpが販売"])

                    # 3. 判定と通知
                    if price and is_official and price <= price_limit:
                        print(f"{item['name']}: 在庫あり判定 ({price}円)")
                        msg = f"**【Amazon在庫あり】**\n**商品名**: {item['name']}\n**価格**: `{price}円`\n**URL**: {item['url']}"
                        send_discord_notify(msg)
                    elif price:
                        status = "Amazon以外（公式在庫なし）" if not is_official else "価格条件外"
                        print(f"-> {item['name']}: {status} ({price}円)")
                    else:
                        print(f"-> {item['name']}: 在庫なし（価格が読み取れません）")

                except Exception as e:
                    print(f"-> {item['name']}: エラー - {type(e).__name__}")
                
                time.sleep(5)
            
            print("1サイクル完了。20秒待機...")
            time.sleep(20)

@app.route("/")
def health_check():
    return "Running"

if __name__ == "__main__":
    threading.Thread(target=check_amazon_task, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
