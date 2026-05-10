import time
import os
import requests
import threading
import re
from playwright.sync_api import sync_playwright
from flask import Flask

app = Flask(__name__)

target_items = [
    {"name": "ロレッタ", "asin": "B004WBF8EG", "url": "https://www.amazon.co.jp/dp/B004WBF8EG"},
    {"name": "PlayStation 5", "asin": "B08SGeDlu", "url": "https://www.amazon.co.jp/dp/B08SGeDlu"},
]

discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

def send_discord_notify(message):
    if not discord_webhook_url: return
    try:
        requests.post(discord_webhook_url, json={"content": message}, timeout=10)
    except: pass

def force_set_japan_location(page):
    """
    Amazonの内部API(address-change)を直接叩いて、
    セッションのお届け先を100-0001(日本)に固定する
    """
    try:
        print("--- お届け先API強制書き換え実行 ---")
        page.goto("https://www.amazon.co.jp/", wait_until="domcontentloaded")
        
        # Amazonの内部APIに直接POSTリクエストを投げてお届け先を1000001に設定
        page.evaluate("""
            fetch('https://www.amazon.co.jp/gp/delivery/ajax/address-change.html', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: 'locationType=LOCATION_INPUT&zipCode=1000001&storeContext=generic&deviceType=web&pageType=Gateway&actionSource=glow'
            })
        """)
        page.wait_for_timeout(2000)
        print("APIリクエスト完了")
    except Exception as e:
        print(f"APIリクエスト失敗: {e}")

def check_amazon_task():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="ja-JP"
        )
        page = context.new_page()

        # 起動時に一度だけお届け先を強制固定
        force_set_japan_location(page)

        print("監視プロセス開始（API強制書き換えモード）")
        while True:
            for item in target_items:
                try:
                    # Amazon公式在庫(smid)を指定してページへ
                    page.goto(f"{item['url']}?smid=AN1VRQENFRJN5", wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(5000)

                    content = page.content()
                    
                    # 1. ページ取得チェック
                    if "CAPTCHA" in page.title() or len(content) < 5000:
                        print(f"-> {item['name']}: [ブロック] ページが正常に読み込めません")
                        continue

                    # 2. 価格抽出（より泥臭い方法で）
                    # ￥マークの後に続く数字をページ全体から探す
                    price = None
                    price_matches = re.findall(r'￥\s?([0-9,]{3,})', content)
                    if price_matches:
                        # ページ内で最初に見つかった3桁以上の数字を価格とする
                        price = int(re.sub(r'\D', '', price_matches[0]))

                    # 3. 在庫/カート判定
                    # カートボタン、または「Amazon.co.jpが販売」の文字列があるか
                    has_cart = "add-to-cart-button" in content or "buy-now-button" in content
                    is_official = "Amazon.co.jp" in content

                    # 4. 判定と出力
                    if has_cart and is_official:
                        display_price = f"{price}円" if price else "価格不明"
                        print(f"{item['name']}: [成功] 公式在庫あり ({display_price})")
                        send_discord_notify(f"**【Amazon在庫復活】**\n{item['name']}\n価格: `{display_price}`\n{item['url']}")
                    else:
                        # 診断情報の出力
                        status = "在庫なし"
                        if "発送できません" in content:
                            status = "地域制限により閲覧不可"
                        elif "在庫切れ" in content:
                            status = "純粋な在庫切れ"
                        print(f"-> {item['name']}: {status} (取得価格: {price})")

                except Exception as e:
                    # 'Error' 以外の詳細な情報を出すために str(e) を使用
                    print(f"-> {item['name']}: エラー - {str(e)[:50]}")
                
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
