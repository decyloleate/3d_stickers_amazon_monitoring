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
    {"name": "PlayStation 5", "url": "https://amzn.asia/d/08SGeDlu"},
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
        
        # 画像・メディアをブロック（CSSはレイアウト維持のため読み込む）
        page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())

        print("監視プロセス開始")
        while True:
            for item in target_items:
                try:
                    page.goto(item['url'], wait_until="domcontentloaded", timeout=40000)
                    page.wait_for_timeout(5000) # レンダリング待ち

                    buybox = None
                    for selector in ["#buybox", "#lp_buybox", "#desktop_buybox", "#combinedBuyBox", "#corePrice_feature_div"]:
                        if page.locator(selector).is_visible():
                            buybox = page.locator(selector)
                            break
                    
                    if buybox:
                        full_text = buybox.inner_text()
                        # 公式販売チェック（柔軟に判定）
                        is_official = any(x in full_text for x in ["Amazon.co.jp", "Amazonによる発送", "Amazon.co.jpが販売"])
                        
                        # 価格抽出（正規表現で数字だけを抜き出す）
                        price = None
                        price_selectors = [".a-price-whole", ".a-offscreen", "#priceblock_ourprice", "span.a-color-price"]
                        for p_sel in price_selectors:
                            el = page.locator(p_sel).first
                            if el.count() > 0:
                                raw_price_text = el.inner_text()
                                digits = re.sub(r'\D', '', raw_price_text) # 数字以外をすべて削除
                                if digits:
                                    price = int(digits)
                                    break

                        if price and is_official and price <= price_limit:
                            print(f"{item['name']}: 在庫あり判定！({price}円)")
                            msg = f"**【Amazon在庫あり】**\n**商品名**: {item['name']}\n**価格**: `{price}円`\n**URL**: {item['url']}"
                            send_discord_notify(msg)
                        elif price:
                            status = "Amazon以外" if not is_official else "価格条件外"
                            print(f"-> {item['name']}: {status} ({price}円)")
                        else:
                            # 価格が取れないがボタンはある場合、テスト通知を送ってみる（任意）
                            print(f"-> {item['name']}: ボタンはありますが価格が不明です。")
                    else:
                        print(f"-> {item['name']}: 在庫なし")

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
