import time
import os
import requests
import threading
import re
from playwright.sync_api import sync_playwright
from flask import Flask

app = Flask(__name__)

# --- 設定項目 ---
# 確実に情報を引き出すため、商品ID(ASIN)を直接指定する形式に変更
target_items = [
    {"name": "ロレッタ", "asin": "B004WBF8EG", "url": "https://www.amazon.co.jp/dp/B004WBF8EG?smid=AN1VRQENFRJN5"},
    {"name": "PlayStation 5", "asin": "B08SGeDlu", "url": "https://www.amazon.co.jp/dp/B08SGeDlu?smid=AN1VRQENFRJN5"},
]

discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

def send_discord_notify(message):
    if not discord_webhook_url: return
    try:
        requests.post(discord_webhook_url, json={"content": message}, timeout=10)
    except: pass

def check_amazon_task():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="ja-JP"
        )
        page = context.new_page()

        print("監視プロセス開始（内部データ直接抽出モデル）")
        while True:
            for item in target_items:
                try:
                    # 商品ページへ
                    page.goto(item['url'], wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(5000)

                    price = None
                    is_official = False

                    # 【解析手法A】ページ内の隠しJSON「data-asin-price」属性等を探す
                    # これが最も確実。HTMLの見た目に関係なくデータが存在する
                    price_element = page.locator("[data-asin-price]").first
                    if price_element.count() > 0:
                        raw_price = price_element.get_attribute("data-asin-price")
                        if raw_price:
                            price = int(float(raw_price))

                    # 【解析手法B】価格が取れない場合、ページ全体の「￥」マーク周辺をスキャン
                    if not price:
                        content = page.content()
                        # "priceAmount":1980 や "price":1980 などのパターンを探す
                        patterns = [r'"priceAmount":(\d+)', r'"price":(\d+)', r'price":\s*"(\d+)"']
                        for pattern in patterns:
                            match = re.search(pattern, content)
                            if match:
                                price = int(match.group(1))
                                break

                    # 【販売元判定】
                    # Amazon公式IDがURLに含まれているため、カートボタンがあれば公式在庫とみなす
                    has_cart = page.locator("#add-to-cart-button, #buy-now-button").is_visible()
                    body_text = page.locator("body").inner_text()
                    is_official_text = any(k in body_text for k in ["Amazon.co.jpが販売", "発送元 Amazon.co.jp"])

                    if has_cart and is_official_text:
                        is_official = True

                    # 最終出力
                    if price and price > 100:
                        if is_official:
                            print(f"{item['name']}: 在庫あり ({price}円)")
                            send_discord_notify(f"**【Amazon在庫復活】**\n{item['name']}\n価格: `{price}円`\n{item['url']}")
                        else:
                            print(f"-> {item['name']}: Amazon以外の販売元 ({price}円)")
                    elif has_cart:
                        # 価格は取れなくてもボタンがあるなら在庫ありとして通知（価格はページで確認してもらう）
                        print(f"{item['name']}: カートボタンあり・価格不明（在庫ありと判断）")
                        send_discord_notify(f"**【Amazon在庫復活（価格不明）】**\n{item['name']}\n※価格の取得に失敗しましたが、カートボタンが出現しています。\n{item['url']}")
                    else:
                        print(f"-> {item['name']}: 在庫なし")

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
