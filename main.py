import time
import os
import requests
import threading
from playwright.sync_api import sync_playwright
from flask import Flask

app = Flask(__name__)

# --- 設定項目 ---
target_items = [
    {"name": "PlayStation 5", "url": "https://amzn.asia/d/08SGeDlu"},
]

price_limit = 99999999999
# 環境変数の読み込み
discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

def send_discord_notify(message):
    if not discord_webhook_url:
        print("【警告】DISCORD_WEBHOOK_URL が設定されていません。")
        return
    try:
        # デバッグ用：送信を試みていることをログに出す
        print(f"Discord通知送信中...")
        response = requests.post(discord_webhook_url, json={"content": message}, timeout=10)
        if response.status_code == 204:
            print("Discord通知の送信に成功しました。")
        else:
            print(f"【エラー】Discord送信失敗（ステータスコード: {response.status_code}）")
    except Exception as e:
        print(f"【エラー】Discord送信中に例外が発生しました: {e}")

def check_amazon_task():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="ja-JP"
        )
        page = context.new_page()
        
        # 安定性を重視し、CSSは読み込ませる（画像・メディアのみブロック）
        page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())

        print("監視プロセス開始")
        while True:
            for item in target_items:
                try:
                    page.goto(item['url'], wait_until="domcontentloaded", timeout=40000)
                    page.wait_for_timeout(5000) # 待機時間を5秒に延長

                    # 複数のカートボックスIDをチェック
                    buybox = None
                    for selector in ["#buybox", "#lp_buybox", "#desktop_buybox", "#combinedBuyBox"]:
                        if page.locator(selector).is_visible():
                            buybox = page.locator(selector)
                            break
                    
                    if buybox:
                        text_content = buybox.inner_text()
                        is_official = "Amazon.co.jp" in text_content
                        
                        # 価格取得セレクタを強化（a-offscreenなども含める）
                        price_selectors = [".a-price-whole", ".a-offscreen", "#priceblock_ourprice", "#kindle-price"]
                        price = None
                        for p_sel in price_selectors:
                            el = buybox.locator(p_sel).first
                            if el.count() > 0:
                                p_text = el.inner_text().replace("￥", "").replace(",", "").strip()
                                if p_text.isdigit():
                                    price = int(p_text)
                                    break

                        if price and is_official and price <= price_limit:
                            print(f"{item['name']}: 公式在庫あり {price}円")
                            msg = f"**【Amazon公式 在庫確認】**\n**商品名**: {item['name']}\n**価格**: `{price}円`\n**URL**: {item['url']}"
                            send_discord_notify(msg)
                        elif price:
                            reason = "Amazon以外" if not is_official else "価格条件外"
                            print(f"-> {item['name']}: {reason} ({price}円)")
                        else:
                            print(f"-> {item['name']}: 在庫ありそうですが、価格の数値が読み取れませんでした。")
                    else:
                        print(f"-> {item['name']}: カートボタンが見つかりません（在庫なし）")

                except Exception as e:
                    print(f"-> {item['name']}: エラー発生 - {type(e).__name__}")
                
                time.sleep(5)
            
            print("1サイクル完了。20秒待機...")
            time.sleep(20)

@app.route("/")
def health_check():
    return "Amazon Bot is running ok."

if __name__ == "__main__":
    threading.Thread(target=check_amazon_task, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
