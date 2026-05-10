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

def inject_stealth_scripts(page):
    """AmazonのBot検知を回避するための偽装スクリプトを注入"""
    # 1. 自動操作フラグ(webdriver)を消去
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    # 2. Chrome特有のプラグイン情報を偽装
    page.add_init_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]})")
    # 3. 言語設定を強制
    page.add_init_script("Object.defineProperty(navigator, 'languages', {get: () => ['ja-JP', 'ja', 'en-US', 'en']})")

def check_amazon_task():
    with sync_playwright() as p:
        # headless=Trueだと検知されやすいため、引数で少しでもブラウザに近づける
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled", # 自動操作を隠す
                "--window-size=1920,1080"
            ]
        )
        
        # ユーザーエージェントを最新のWindows Chromeに偽装
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="ja-JP",
            timezone_id="Asia/Tokyo"
        )
        
        page = context.new_page()
        inject_stealth_scripts(page)

        print("監視プロセス開始（ステルス偽装＆診断モード）")
        while True:
            for item in target_items:
                try:
                    # Amazonへのアクセス
                    response = page.goto(item['url'], wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(5000)

                    page_title = page.title()
                    
                    # --- 診断：Botブロック検知 ---
                    if "CAPTCHA" in page_title or "ご迷惑をおかけして" in page_title:
                        print(f"-> {item['name']}: [ブロック検知] Amazon CAPTCHA または エラーページに弾かれました。")
                        continue
                    if response and response.status in [403, 503]:
                        print(f"-> {item['name']}: [ブロック検知] アクセス拒否 (HTTP {response.status})")
                        continue

                    # ブロックされていない場合の解析
                    price = None
                    is_official = False
                    content = page.content()

                    # 【解析手法】埋め込みJSON（data-asin-price）や生テキストからの抽出
                    price_element = page.locator("[data-asin-price]").first
                    if price_element.count() > 0:
                        raw_price = price_element.get_attribute("data-asin-price")
                        if raw_price:
                            price = int(float(raw_price))

                    if not price:
                        patterns = [r'"priceAmount":\s*(\d+)', r'"price":\s*(\d+)']
                        for pattern in patterns:
                            match = re.search(pattern, content)
                            if match:
                                price = int(match.group(1))
                                break

                    # 販売元とカートボタンの判定
                    has_cart = page.locator("#add-to-cart-button, #buy-now-button").is_visible()
                    is_official = any(k in content for k in ["Amazon.co.jpが販売", "発送元 Amazon.co.jp", "Amazon.co.jp directly"])

                    # --- 最終判定 ---
                    if price and price > 100:
                        if is_official or has_cart:
                            print(f"{item['name']}: [成功] 在庫あり ({price}円)")
                            send_discord_notify(f"**【Amazon在庫復活】**\n{item['name']}\n価格: `{price}円`\n{item['url']}")
                        else:
                            print(f"-> {item['name']}: [警告] Amazon以外の販売元 ({price}円)")
                    elif has_cart:
                        print(f"{item['name']}: [部分成功] カートボタンあり・価格隠蔽状態")
                    else:
                        print(f"-> {item['name']}: 在庫なし（正常にページは取得済）")

                except Exception as e:
                    print(f"-> {item['name']}: エラー - {type(e).__name__}")
                
                time.sleep(15) # Amazonへの負荷を減らしブロックを避けるため待機を延長
            
            print("1サイクル完了。次へ...")
            time.sleep(30)

@app.route("/")
def health_check():
    return "Monitoring"

if __name__ == "__main__":
    threading.Thread(target=check_amazon_task, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
