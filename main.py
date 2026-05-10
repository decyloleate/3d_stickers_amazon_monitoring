import time
import os
import requests
import threading
from playwright.sync_api import sync_playwright
from flask import Flask

app = Flask(__name__)

# --- 設定項目 ---
target_items = [
    # {"name": "ぴだんぶい", "url": "https://www.amazon.co.jp/%E3%82%B5%E3%83%B3%E3%82%B9%E3%82%BF%E3%83%BC%E6%96%87%E5%85%B7-Sun-Star-Stationery-%E3%82%B5%E3%83%B3%E3%83%AA%E3%82%AA%E3%82%AD%E3%83%A3%E3%83%A9%E3%82%AF%E3%82%BF%E3%83%BC%E3%82%BA-S8815135/dp/B0G2RP9RMN?ref_=ast_sto_dp"},
    # {"name": "みみっち", "url": "https://www.amazon.co.jp/%E3%82%B5%E3%83%B3%E3%82%B9%E3%82%BF%E3%83%BC%E6%96%87%E5%85%B7-Sun-Star-Stationery-%E3%83%9C%E3%83%B3%E3%83%9C%E3%83%B3%E3%83%89%E3%83%AD%E3%83%83%E3%83%97%E3%82%B7%E3%83%BC%E3%83%AB-S8812578/dp/B0F4CZNHWC?ref_=ast_sto_dp"},
    # {"name": "まめっち", "url": "https://www.amazon.co.jp/%E3%82%B5%E3%83%B3%E3%82%B9%E3%82%BF%E3%83%BC%E6%96%87%E5%85%B7-Sun-Star-Stationery-%E3%83%9C%E3%83%B3%E3%83%9C%E3%83%B3%E3%83%89%E3%83%AD%E3%83%83%E3%83%97%E3%82%B7%E3%83%BC%E3%83%AB-S8812543/dp/B0F4CWWMTM?ref_=ast_sto_dp"},
    # {"name": "スヌーピー", "url": "https://www.amazon.co.jp/%E3%82%B5%E3%83%B3%E3%82%B9%E3%82%BF%E3%83%BC%E6%96%87%E5%85%B7-Sun-Star-Stationery-%E3%83%9C%E3%83%B3%E3%83%9C%E3%83%B3%E3%83%89%E3%83%AD%E3%83%83%E3%83%97%E3%82%B7%E3%83%BC%E3%83%AB-S8815143/dp/B0G2RSZ4KX?ref_=ast_sto_dp"},
    # {"name": "キティ(pink)", "url": "https://www.amazon.co.jp/%E3%82%B5%E3%83%B3%E3%82%B9%E3%82%BF%E3%83%BC%E6%96%87%E5%85%B7-Sun-Star-Stationery-%E3%82%B5%E3%83%B3%E3%83%AA%E3%82%AA%E3%82%AD%E3%83%A3%E3%83%A9%E3%82%AF%E3%82%BF%E3%83%BC%E3%82%BA-S8815070/dp/B0G2RQL3RG?ref_=ast_sto_dp"},
    # {"name": "キティ(red)", "url": "https://www.amazon.co.jp/%E3%82%B5%E3%83%B3%E3%82%B9%E3%82%BF%E3%83%BC%E6%96%87%E5%85%B7-Sun-Star-Stationery-%E3%82%B5%E3%83%B3%E3%83%AA%E3%82%AA%E3%82%AD%E3%83%A3%E3%83%A9%E3%82%AF%E3%82%BF%E3%83%BC%E3%82%BA-S8815062/dp/B0G2RSS3HV?ref_=ast_sto_dp"},
    # {"name": "マイメロ", "url": "https://www.amazon.co.jp/%E3%82%B5%E3%83%B3%E3%82%B9%E3%82%BF%E3%83%BC%E6%96%87%E5%85%B7-Sun-Star-Stationery-%E3%82%B5%E3%83%B3%E3%83%AA%E3%82%AA%E3%82%AD%E3%83%A3%E3%83%A9%E3%82%AF%E3%82%BF%E3%83%BC%E3%82%BA-S8815089/dp/B0G2RQ7QBP?ref_=ast_sto_dp"},
    # {"name": "めめっち", "url": "https://www.amazon.co.jp/%E3%82%B5%E3%83%B3%E3%82%B9%E3%82%BF%E3%83%BC%E6%96%87%E5%85%B7-%E3%81%9F%E3%81%BE%E3%81%94%E3%81%A3%E3%81%A1-%E3%83%9C%E3%83%B3%E3%83%9C%E3%83%B3%E3%83%89%E3%83%AD%E3%83%83%E3%83%97%E3%82%B7%E3%83%BC%E3%83%AB-%E3%82%81%E3%82%81%E3%81%A3%E3%81%A1-S8812551/dp/B0F4D3KKGJ?ref_=ast_sto_dp"},
    {"name": "クロミ", "url": "https://www.amazon.co.jp/%E3%82%B5%E3%83%B3%E3%82%B9%E3%82%BF%E3%83%BC%E6%96%87%E5%85%B7-Sun-Star-Stationery-%E3%82%B5%E3%83%B3%E3%83%AA%E3%82%AA%E3%82%AD%E3%83%A3%E3%83%A9%E3%82%AF%E3%82%BF%E3%83%BC%E3%82%BA-S8815127/dp/B0G2RPXXY8?ref_=ast_sto_dp"},
    # {"name": "ミニ エイリアン", "url": "https://www.amazon.co.jp/%E3%82%B5%E3%83%B3%E3%82%B9%E3%82%BF%E3%83%BC%E6%96%87%E5%85%B7-Sun-Star-Stationery-%E3%83%9C%E3%83%B3%E3%83%9C%E3%83%B3%E3%83%89%E3%83%AD%E3%83%83%E3%83%97%E3%82%B7%E3%83%BC%E3%83%AB-S8815054/dp/B0G2RPNBLX?ref_=ast_sto_dp"},
    # {"name": "ちいかわ", "url": "https://www.amazon.co.jp/%E3%82%B5%E3%83%B3%E3%82%B9%E3%82%BF%E3%83%BC%E6%96%87%E5%85%B7-Sun-Star-Stationery-%E3%83%9C%E3%83%B3%E3%83%9C%E3%83%B3%E3%83%89%E3%83%AD%E3%83%83%E3%83%97%E3%82%B7%E3%83%BC%E3%83%AB-S8542899/dp/B0FN3YRZNY?ref_=ast_sto_dp"},
    # {"name": "ハチワレ", "url": "https://www.amazon.co.jp/%E3%82%B5%E3%83%B3%E3%82%B9%E3%82%BF%E3%83%BC%E6%96%87%E5%85%B7-Sun-Star-Stationery-%E3%83%9C%E3%83%B3%E3%83%9C%E3%83%B3%E3%83%89%E3%83%AD%E3%83%83%E3%83%97%E3%82%B7%E3%83%BC%E3%83%AB-S8542902/dp/B0FN41LJVC?ref_=ast_sto_dp"},
    # {"name": "うさぎ", "url": "https://www.amazon.co.jp/%E3%82%B5%E3%83%B3%E3%82%B9%E3%82%BF%E3%83%BC%E6%96%87%E5%85%B7-Sun-Star-Stationery-%E3%83%9C%E3%83%B3%E3%83%9C%E3%83%B3%E3%83%89%E3%83%AD%E3%83%83%E3%83%97%E3%82%B7%E3%83%BC%E3%83%AB-S8542910/dp/B0FN42WHFR?ref_=ast_sto_dp"},
    # {"name": "ちいハチうさ", "url": "https://www.amazon.co.jp/%E3%82%B5%E3%83%B3%E3%82%B9%E3%82%BF%E3%83%BC%E6%96%87%E5%85%B7-Sun-Star-Stationery-%E3%81%A1%E3%81%84%E3%81%8B%E3%82%8F%C3%97%E3%83%8F%E3%83%81%E3%83%AF%E3%83%AC%C3%97%E3%81%86%E3%81%95%E3%81%8E-S8542945/dp/B0FN42TGW4?ref_=ast_sto_dp"},
    # {"name": "モモンガ", "url": "https://www.amazon.co.jp/%E3%82%B5%E3%83%B3%E3%82%B9%E3%82%BF%E3%83%BC%E6%96%87%E5%85%B7-Sun-Star-Stationery-%E3%83%9C%E3%83%B3%E3%83%9C%E3%83%B3%E3%83%89%E3%83%AD%E3%83%83%E3%83%97%E3%82%B7%E3%83%BC%E3%83%AB-S8542929/dp/B0FN3ZW94L?ref_=ast_sto_dp"},
    # {"name": "古本屋", "url": "https://www.amazon.co.jp/%E3%82%B5%E3%83%B3%E3%82%B9%E3%82%BF%E3%83%BC%E6%96%87%E5%85%B7-Sun-Star-Stationery-%E3%83%9C%E3%83%B3%E3%83%9C%E3%83%B3%E3%83%89%E3%83%AD%E3%83%83%E3%83%97%E3%82%B7%E3%83%BC%E3%83%AB-S8542929/dp/B0FN3ZW94L?ref_=ast_sto_dp"},
    # {"name": "ちいかわニコニコ", "url": "https://www.amazon.co.jp/%E3%82%B5%E3%83%B3%E3%82%B9%E3%82%BF%E3%83%BC%E6%96%87%E5%85%B7-Sun-Star-Stationery-%E3%83%9C%E3%83%B3%E3%83%9C%E3%83%B3%E3%83%89%E3%83%AD%E3%83%83%E3%83%97%E3%82%B7%E3%83%BC%E3%83%AB-S8542953/dp/B0FN412KVB?ref_=ast_sto_dp"},
    # {"name": "ちいかわポーズ", "url": "https://www.amazon.co.jp/%E3%82%B5%E3%83%B3%E3%82%B9%E3%82%BF%E3%83%BC%E6%96%87%E5%85%B7-Sun-Star-Stationery-%E3%83%9C%E3%83%B3%E3%83%9C%E3%83%B3%E3%83%89%E3%83%AD%E3%83%83%E3%83%97%E3%82%B7%E3%83%BC%E3%83%AB-S8542961/dp/B0FN42SFNB?ref_=ast_sto_dp"},
    # {"name": "くちぱっち", "url": "https://www.amazon.co.jp/%E3%82%B5%E3%83%B3%E3%82%B9%E3%82%BF%E3%83%BC%E6%96%87%E5%85%B7-%E3%81%9F%E3%81%BE%E3%81%94%E3%81%A3%E3%81%A1-%E3%83%9C%E3%83%B3%E3%83%9C%E3%83%B3%E3%83%89%E3%83%AD%E3%83%83%E3%83%97%E3%82%B7%E3%83%BC%E3%83%AB-%E3%81%8F%E3%81%A1%E3%81%B1%E3%81%A3%E3%81%A1-S8812560/dp/B0F4CZTGD9?ref_=ast_sto_dp"},
    # {"name": "Nintendo Switch 2", "url": "https://amzn.asia/d/02LmnGzL"},
     {"name": "PlayStation 5", "url": "https://amzn.asia/d/08SGeDlu"},
    # {"name": "", "url": ""},
]

price_limit = 99999999999
# セキュリティのため環境変数から取得するように変更
discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

def send_discord_notify(message):
    if not discord_webhook_url: return
    try:
        requests.post(discord_webhook_url, json={"content": message}, timeout=5)
    except:
        pass

def check_amazon_task():
    with sync_playwright() as p:
        # メモリ制限対策の引数を指定してブラウザを起動
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ja-JP"
        )
        page = context.new_page()
        
        # 高速化: 画像、CSS、フォントの読み込みを強制ブロック
        page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] else route.continue_())

        print("監視プロセス開始")
        while True:
            for item in target_items:
                try:
                    page.goto(item['url'], timeout=30000)
                    buybox = page.locator("#buybox")
                    buybox.wait_for(state="attached", timeout=10000)
                    
                    text_content = buybox.inner_text()
                    is_official = "Amazon.co.jp" in text_content
                    
                    price_element = buybox.locator(".a-price-whole").first
                    if price_element.count() > 0:
                        price = int(price_element.inner_text().replace(",", "").strip())
                        
                        if is_official and price <= price_limit:
                            print(f"{item['name']}: 公式在庫あり {price}円")
                            msg = f"**【Amazon公式 在庫確認】**\n**商品名**: {item['name']}\n**価格**: `{price}円`\n**URL**: {item['url']}"
                            send_discord_notify(msg)
                        else:
                            print(f"-> {item['name']}: マケプレ ({price}円) または条件外")
                    else:
                        print(f"-> {item['name']}: 在庫なし/価格取得不可")

                except Exception as e:
                    print(f"-> {item['name']}: エラー詳細: {type(e).__name__} - {e}")
                    try:
                        print(f"   [デバッグ] 現在のページタイトル: {page.title()}")
                    except:
                        pass    
                
                time.sleep(2)
            
            print("1サイクル完了。20秒待機...")
            time.sleep(20)
# Renderのポートバインディング対策（死活監視用エンドポイント）
@app.route("/")
def health_check():
    return "Amazon Bot is running ok."

if __name__ == "__main__":
    # 監視タスクをバックグラウンドで開始
    threading.Thread(target=check_amazon_task, daemon=True).start()
    
    # Flaskサーバー起動
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
