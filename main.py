import time
import os
import requests
import threading
import re
from playwright.sync_api import sync_playwright
from flask import Flask

app = Flask(__name__)

# --- 設定項目 ---
# URLに ?language=ja_JP を付けて日本語・日本向けを強調
target_items = [
    {"name": "ロレッタ", "url": "https://www.amazon.co.jp/dp/B004WBF8EG?language=ja_JP"},
    {"name": "PlayStation 5", "url": "https://www.amazon.co.jp/dp/B08SGeDlu?language=ja_JP"},
]

discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

def send_discord_notify(message):
    if not discord_webhook_url: return
    try:
        requests.post(discord_webhook_url, json={"content": message}, timeout=10)
    except: pass

def inject_session_cookies(context):
    """
    画面操作なしで「日本のお届け先」を強制セットするCookieを注入する
    """
    # 郵便番号100-0001に関連する情報をCookieとして設定
    cookies = [
        {
            "name": "i18n-prefs",
            "value": "JPY",
            "domain": ".amazon.co.jp",
            "path": "/"
        },
        {
            "name": "lc-acjp",
            "value": "ja_JP",
            "domain": ".amazon.co.jp",
            "path": "/"
        }
    ]
    context.add_cookies(cookies)

def check_amazon_task():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        # 日本語環境を徹底
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
            viewport={'width': 1280, 'height': 800}
        )
        
        # Cookieを注入して住所変更の手間を省く
        inject_session_cookies(context)
        page = context.new_page()

        print("監視プロセス開始（Cookie注入モード）")
        while True:
            for item in target_items:
                try:
                    # networkidleだと時間がかかる場合があるのでdomcontentloadedで判定
                    page.goto(item['url'], wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(5000)

                    # --- 米国IP対策: 「すべての出品を見る」ボタンがあるかチェック ---
                    # カートボタンがなくても「すべての出品」から価格が拾える場合がある
                    all_offers_btn = page.locator("a[aria-label='すべての出品を見る']").first
                    if all_offers_btn.is_visible() and not page.locator(".a-price-whole").first.is_visible():
                         all_offers_btn.click()
                         page.wait_for_timeout(3000)

                    # --- 価格取得ロジックの再強化 ---
                    price = None
                    # 1. メイン価格エリア 2. 定期おトク便 3. 右側の価格一覧
                    selectors = [
                        "#corePriceDisplay_desktop_feature_div .a-price-whole",
                        "#corePrice_desktop .a-price-whole",
                        ".a-price.a-text-price.a-size-medium .a-offscreen", # セール時
                        "#kindle-price",
                        ".a-color-price"
                    ]
                    
                    for sel in selectors:
                        el = page.locator(sel).first
                        if el.is_visible():
                            raw = el.inner_text()
                            # ￥1,980 (￥7/g) のような表記から最初の数字の塊を抜く
                            match = re.search(r'([0-9,]{3,})', raw)
                            if match:
                                val = int(re.sub(r'\D', '', match.group(1)))
                                if val > 100:
                                    price = val
                                    break

                    # --- 販売元判定 ---
                    is_official = False
                    # ページ全体のテキストからAmazonが販売している形跡を探す
                    body_text = page.locator("body").inner_text()
                    official_keywords = ["Amazon.co.jpが販売", "発送元 Amazon.co.jp", "Amazonによる発送"]
                    is_official = any(k in body_text for k in official_keywords)

                    # --- 判定 ---
                    if price:
                        if is_official:
                            print(f"{item['name']}: 在庫あり判定 ({price}円)")
                            send_discord_notify(f"**【Amazon在庫あり】**\n{item['name']}\n価格: `{price}円`\n{item['url']}")
                        else:
                            # 転売価格でも価格が拾えているならログに残す
                            print(f"-> {item['name']}: Amazon以外の販売元 ({price}円)")
                    else:
                        print(f"-> {item['name']}: 在庫なし（価格取得不可）")

                except Exception as e:
                    print(f"-> {item['name']}: エラー - {type(e).__name__}")
                
                time.sleep(15)
            
            print("1サイクル完了。次へ...")
            time.sleep(30)

@app.route("/")
def health_check():
    return "Running"

if __name__ == "__main__":
    threading.Thread(target=check_amazon_task, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
