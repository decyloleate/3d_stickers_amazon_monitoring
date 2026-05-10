import time
import os
import requests
import threading
import re
import json
from playwright.sync_api import sync_playwright
from flask import Flask

app = Flask(__name__)

# --- 設定項目 ---
# smid=AN1VRQENFRJN5 を付与してAmazon公式販売分を強制指定
target_items = [
    {"name": "ロレッタ", "url": "https://www.amazon.co.jp/dp/B004WBF8EG?smid=AN1VRQENFRJN5&psc=1"},
    {"name": "PlayStation 5", "url": "https://www.amazon.co.jp/dp/B08SGeDlu?smid=AN1VRQENFRJN5&psc=1"},
]

discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

def send_discord_notify(message):
    if not discord_webhook_url: return
    try:
        requests.post(discord_webhook_url, json={"content": message}, timeout=10)
    except: pass

def check_amazon_task():
    with sync_playwright() as p:
        # プロキシなしで安定させるための最小限の引数
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="ja-JP",
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()

        print("監視プロセス開始（究極解析モード）")
        while True:
            for item in target_items:
                try:
                    # タイムアウトを長めに設定
                    page.goto(item['url'], wait_until="domcontentloaded", timeout=60000)
                    # 重要な要素が出るまで最大10秒待機
                    page.wait_for_selector("body", timeout=10000)
                    page.wait_for_timeout(5000)

                    price = None
                    is_official = False

                    # 手法1: ページ内の「twister-js-init-dpx-data」というJSONから価格を抜く（最も確実）
                    scripts = page.locator("script[type='text/javascript']").all()
                    for script in scripts:
                        content = script.inner_html()
                        if "priceAmount" in content:
                            # 正規表現で価格らしき数字（例: 1980.0）を探す
                            match = re.search(r'"priceAmount":\s*(\d+)', content)
                            if match:
                                price = int(match.group(1))
                                break

                    # 手法2: JSONで見つからない場合、従来のセレクタをさらに広範囲で探す
                    if not price:
                        selectors = [
                            ".apexPriceToPay .a-offscreen",
                            "#corePriceDisplay_desktop_feature_div .a-price-whole",
                            "#kindle-price",
                            "span.a-color-price"
                        ]
                        for sel in selectors:
                            el = page.locator(sel).first
                            if el.is_visible():
                                raw = el.inner_text()
                                match = re.search(r'([0-9,]{3,})', raw)
                                if match:
                                    price = int(re.sub(r'\D', '', match.group(1)))
                                    break

                    # 販売元判定の強化
                    # URLに公式IDを含めているが、念のため画面上のテキストでも確認
                    page_content = page.content()
                    official_keywords = ["Amazon.co.jpが販売", "Amazon.co.jp directly", "発送元 Amazon.co.jp"]
                    is_official = any(k in page_content for k in official_keywords)

                    # 判定とログ出力
                    if price and price > 100:
                        if is_official:
                            print(f"{item['name']}: 公式在庫あり判定 ({price}円)")
                            send_discord_notify(f"**【Amazon公式在庫復活】**\n{item['name']}\n価格: `{price}円`\n{item['url']}")
                        else:
                            print(f"-> {item['name']}: Amazon以外が販売中 ({price}円)")
                    else:
                        # 最終手段：画面上に「カートに入れる」系のボタンがあるかだけで判定
                        if "add-to-cart-button" in page_content:
                            print(f"-> {item['name']}: カートボタンあり（価格不明）")
                        else:
                            print(f"-> {item['name']}: 在庫なし（価格・ボタン共に取得不可）")

                except Exception as e:
                    print(f"-> {item['name']}: エラー発生 - {type(e).__name__}")
                
                time.sleep(10)
            
            print("1サイクル完了。次へ...")
            time.sleep(30)

@app.route("/")
def health_check():
    return "Monitoring"

if __name__ == "__main__":
    threading.Thread(target=check_amazon_task, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
