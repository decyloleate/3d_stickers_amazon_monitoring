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
    {"name": "ロレッタ", "url": "https://www.amazon.co.jp/dp/B004WBF8EG?smid=AN1VRQENFRJN5"},
    {"name": "PlayStation 5", "url": "https://www.amazon.co.jp/dp/B08SGeDlu?smid=AN1VRQENFRJN5"},
]

discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

def send_discord_notify(message):
    if not discord_webhook_url: return
    try:
        requests.post(discord_webhook_url, json={"content": message}, timeout=10)
    except: pass

def check_amazon_task():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--window-size=1920,1080"
            ]
        )
        
        # 【最重要】Googlebot(スマホ版)に偽装し、日本のIPヘッダーを付与
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
            extra_http_headers={
                "Accept-Language": "ja-JP,ja;q=0.9",
                "X-Forwarded-For": "133.232.0.0" # 日本のIP帯域をアピール
            }
        )
        
        page = context.new_page()

        print("監視プロセス開始（Googlebot偽装＆ステータス直読みモード）")
        while True:
            for item in target_items:
                try:
                    response = page.goto(item['url'], wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(5000)

                    if "CAPTCHA" in page.title() or "ご迷惑をおかけして" in page.title():
                        print(f"-> {item['name']}: [ブロック検知] CAPTCHAやエラー画面")
                        continue

                    # 【解析1】Amazonが画面に表示している「在庫状況テキスト」を直接抜き出す
                    availability_text = "ステータス表記なし"
                    avail_locator = page.locator("#availability, #outOfStock, .qa-availability-message").first
                    if avail_locator.is_visible():
                        # 改行を消して1行のテキストにする
                        availability_text = re.sub(r'\s+', ' ', avail_locator.inner_text().strip())

                    # 【解析2】価格とカートの取得
                    price = None
                    content = page.content()

                    # Googlebot向けに簡略化されたHTMLから価格を探す
                    price_match = re.search(r'"priceAmount":\s*(\d+)', content) or re.search(r'data-asin-price="(\d+\.?\d*)"', content)
                    if price_match:
                        price = int(float(price_match.group(1)))
                    else:
                        for sel in [".a-price-whole", "#priceblock_ourprice", ".apexPriceToPay"]:
                            el = page.locator(sel).first
                            if el.is_visible():
                                digits = re.sub(r'\D', '', el.inner_text())
                                if digits:
                                    price = int(digits)
                                    break

                    has_cart = page.locator("#add-to-cart-button, #buy-now-button, #submit\\.add-to-cart").is_visible()
                    is_official = any(k in content for k in ["Amazon.co.jpが販売", "発送元 Amazon.co.jp", "Amazon.co.jp directly"])

                    # --- 最終判定 ---
                    if price and price > 100 and (is_official or has_cart):
                        print(f"{item['name']}: [成功] 在庫あり ({price}円) - 状態: [{availability_text}]")
                        send_discord_notify(f"**【Amazon在庫復活】**\n{item['name']}\n価格: `{price}円`\n{item['url']}")
                    elif has_cart:
                        print(f"{item['name']}: [部分成功] カートあり(価格不明) - 状態: [{availability_text}]")
                    else:
                        # 失敗した場合でも、Amazonが何と言って拒否しているかをログに出す
                        print(f"-> {item['name']}: 画面判定 [{availability_text}] (取得価格: {price}円)")

                except Exception as e:
                    print(f"-> {item['name']}: エラー - {type(e).__name__}")
                
                time.sleep(15)
            
            print("1サイクル完了。次へ...")
            time.sleep(30)

@app.route("/")
def health_check():
    return "Monitoring"

if __name__ == "__main__":
    threading.Thread(target=check_amazon_task, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
