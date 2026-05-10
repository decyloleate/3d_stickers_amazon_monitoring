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
    {"name": "ロレッタ", "asin": "B004WBF8EG"},
    {"name": "PlayStation 5", "asin": "B08SGeDlu"},
]

discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

def send_discord_notify(message):
    if not discord_webhook_url: return
    try:
        requests.post(discord_webhook_url, json={"content": message}, timeout=10)
    except: pass

def check_amazon_task():
    with sync_playwright() as p:
        # ステルス性を維持しつつPC版として動作
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="ja-JP"
        )
        page = context.new_page()

        print("監視プロセス開始（AOD裏ページ解析モデル）")
        while True:
            for item in target_items:
                try:
                    # 【重要】商品詳細ページではなく「すべての出品」ページを直接開く
                    # このURLは「お届け先」による価格隠蔽がされにくい特殊なページです
                    aod_url = f"https://www.amazon.co.jp/gp/product/ajax/ref=dp_aod_ALL_mbc?asin={item['asin']}&experienceId=aodAjaxMain"
                    
                    page.goto(aod_url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(3000)

                    content = page.content()
                    
                    # 1. ページが正常に開けているか確認
                    if "CAPTCHA" in page.title() or len(content) < 500:
                        print(f"-> {item['name']}: [ブロック] ページを正常に読み込めませんでした")
                        continue

                    # 2. 「Amazon.co.jpが販売」というブロックを探す
                    # AODページ内では各販売者が独立した div で構成されています
                    price = None
                    
                    # AODページ特有の価格セレクタ（.a-price .a-offscreen）をスキャン
                    # Amazon.co.jpが販売している行の価格を特定する
                    offers = page.locator("#aod-offer").all()
                    for offer in offers:
                        offer_text = offer.inner_text()
                        if "Amazon.co.jp" in offer_text:
                            # このブロック内に価格があるか確認
                            price_el = offer.locator(".a-price .a-offscreen").first
                            if price_el.is_visible():
                                raw_price = price_el.inner_text()
                                digits = re.sub(r'\D', '', raw_price)
                                if digits:
                                    price = int(digits)
                                    break
                    
                    # バックアップ：もし上記で見つからない場合、ページ全体の最初の価格を拾う
                    if not price:
                        price_match = re.search(r'￥\s?([0-9,]+)', content)
                        if price_match:
                            price = int(re.sub(r'\D', '', price_match.group(1)))

                    # 3. 判定
                    # AODページで「Amazon.co.jp」という文字があり、価格が取れれば在庫あり
                    if price and price > 100 and "Amazon.co.jp" in content:
                        print(f"{item['name']}: [成功] 公式在庫あり ({price}円)")
                        item_url = f"https://www.amazon.co.jp/dp/{item['asin']}"
                        send_discord_notify(f"**【Amazon在庫復活】**\n{item['name']}\n価格: `{price}円` (AOD解析)\n{item_url}")
                    else:
                        print(f"-> {item['name']}: 在庫なし（AODページに公式販売なし）")

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
