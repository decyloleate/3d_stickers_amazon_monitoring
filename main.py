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
    {"name": "ロレッタ", "url": "https://amzn.asia/d/04Hjs6ii"},
    {"name": "PlayStation 5", "url": "https://amzn.asia/d/08SGeDlu"},
]

discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

def send_discord_notify(message):
    if not discord_webhook_url: return
    try:
        requests.post(discord_webhook_url, json={"content": message}, timeout=10)
    except Exception as e:
        print(f"Discord送信エラー: {e}")

def set_japan_location(page):
    """お届け先を日本の郵便番号(100-0001)に設定する"""
    try:
        print("お届け先を日本(100-0001)に設定中...")
        page.goto("https://www.amazon.co.jp/", wait_until="domcontentloaded")
        
        # お届け先変更ボタンをクリック
        page.click("#nav-global-location-slot")
        page.wait_for_selector("#GLUXZipUpdateInput", timeout=10000)
        
        # 郵便番号入力 (1000001)
        page.fill("#GLUXZipUpdateInput", "1000001")
        # 「設定」ボタンをクリック
        page.click("#GLUXZipUpdate")
        
        # 反映待ち（確認ボタンが出る場合がある）
        page.wait_for_timeout(2000)
        if page.locator("#GLUXConfirmClose").is_visible():
            page.click("#GLUXConfirmClose")
        
        page.wait_for_timeout(3000) # ページ更新待ち
        print("位置設定完了")
    except Exception as e:
        print(f"位置設定失敗（続行します）: {e}")

def check_amazon_task():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="ja-JP"
        )
        page = context.new_page()
        
        # 最初に一度だけ日本国内に設定
        set_japan_location(page)

        print("監視プロセス開始")
        while True:
            for item in target_items:
                try:
                    # 毎回新鮮な状態で開く
                    page.goto(item['url'], wait_until="networkidle", timeout=60000)
                    page.wait_for_timeout(3000)

                    # 1. 厳密な価格取得（メイン価格エリアに限定）
                    price = None
                    # 画面右側の購入枠（BuyBox）内の数字だけを狙う
                    price_box = page.locator("#corePrice_desktop, #corePriceDisplay_desktop_feature_div, #sns-base-price").first
                    
                    if price_box.is_visible():
                        price_text = price_box.inner_text()
                        # 「￥ 1,980」のような形式から数字だけを抽出
                        # 最初に現れる3桁以上の数字、またはカンマを含む数字を優先
                        match = re.search(r'([0-9,]{3,})', price_text)
                        if match:
                            price = int(re.sub(r'\D', '', match.group(1)))

                    # 2. 販売元チェック
                    is_official = False
                    buybox = page.locator("#desktop_buybox, #rightCol").first
                    if buybox.is_visible():
                        bb_text = buybox.inner_text()
                        is_official = any(x in bb_text for x in ["Amazon.co.jp", "Amazonによる発送", "Amazon.co.jpが販売"])

                    # 3. 判定
                    if price and is_official:
                        # 100円以下の数値はゴミデータとして無視
                        if price < 100:
                            print(f"-> {item['name']}: 低すぎる数値を無視しました({price}円)")
                            continue
                            
                        print(f"{item['name']}: 在庫あり判定 ({price}円)")
                        msg = f"**【Amazon在庫あり】**\n**商品名**: {item['name']}\n**価格**: `{price}円`\n**URL**: {item['url']}"
                        send_discord_notify(msg)
                    elif price:
                        print(f"-> {item['name']}: 公式在庫なし (現在値: {price}円)")
                    else:
                        print(f"-> {item['name']}: 在庫なし（価格取得不可）")

                except Exception as e:
                    print(f"-> {item['name']}: エラー - {type(e).__name__}")
                
                time.sleep(10)
            
            print("1サイクル完了。次へ...")
            time.sleep(30)

@app.route("/")
def health_check():
    return "Running"

if __name__ == "__main__":
    threading.Thread(target=check_amazon_task, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
