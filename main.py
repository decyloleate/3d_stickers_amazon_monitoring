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
]

discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

def send_discord_notify(message):
    if not discord_webhook_url: return
    try:
        requests.post(discord_webhook_url, json={"content": message}, timeout=10)
    except Exception as e:
        print(f"Discord送信エラー: {e}")

def set_japan_location(page):
    """お届け先を日本の郵便番号(100-0001)に設定する（強化版）"""
    try:
        print("お届け先を日本(100-0001)に設定中...")
        page.goto("https://www.amazon.co.jp/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        # 1. 邪魔なログインポップアップやバナーを消去
        # 画面の適当な場所をクリックしてポップアップを消す
        page.mouse.click(10, 10)
        page.wait_for_timeout(1000)

        # 2. お届け先ボタンをクリック（複数の候補から探す）
        location_btn = page.locator("#nav-global-location-slot, #glow-ingress-block, a[data-nav-role='select-location']").first
        if location_btn.is_visible():
            location_btn.click()
        else:
            print("お届け先ボタンが見つかりません。")
            return

        # 3. 郵便番号入力フォームを待機（タイムアウトを伸ばし、複数のセレクタを試行）
        # アメリカからのアクセス時はIDが変わることがあるため汎用的なセレクタを使用
        input_selector = "input#GLUXZipUpdateInput, input[aria-label='郵便番号の最初の3桁'], input.GLUX_Full_Width"
        try:
            page.wait_for_selector(input_selector, timeout=15000)
        except:
            print("入力フォームが出現しません。ページ全体のHTMLをログに出力します（解析用）")
            # 失敗した場合、今の画面の状態を確認するために少し待ってからHTML構造を把握
            return

        # 4. 郵便番号入力 (1000001)
        page.fill(input_selector, "1000001")
        
        # 5. 「設定」または「適用」ボタンをクリック
        apply_btn = page.locator("#GLUXZipUpdate, input[aria-labelledby='GLUXZipUpdate-announce']").first
        apply_btn.click()
        
        # 6. 反映後の「完了」や「続行」ボタンを処理
        page.wait_for_timeout(3000)
        # 「続行」ボタンなどが出る場合がある
        final_btns = ["#GLUXConfirmClose", ".a-popover-footer input", "button[name='glowDoneButton']"]
        for btn in final_btns:
            el = page.locator(btn).first
            if el.is_visible():
                el.click()
                break

        page.wait_for_timeout(2000)
        print("位置設定完了")
        
    except Exception as e:
        print(f"位置設定中に致命的なエラー: {e}")

def check_amazon_task():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="ja-JP",
            viewport={'width': 1280, 'height': 800} # 画面サイズを固定してレイアウト崩れを防ぐ
        )
        page = context.new_page()
        
        # 起動時に日本国内に設定を試みる
        set_japan_location(page)

        print("監視プロセス開始")
        while True:
            for item in target_items:
                try:
                    # 遷移を安定させるため、wait_untilをnetworkidleに変更
                    page.goto(item['url'], wait_until="networkidle", timeout=60000)
                    page.wait_for_timeout(5000)

                    # --- 価格取得 ---
                    price = None
                    # 米国IPから見た時の特殊な価格エリアも考慮
                    price_selectors = [
                        "#corePrice_desktop .a-price-whole",
                        "#corePriceDisplay_desktop_feature_div .a-price-whole",
                        "#sns-base-price .a-price-whole",
                        "#kindle-price",
                        ".a-color-price"
                    ]
                    
                    for sel in price_selectors:
                        el = page.locator(sel).first
                        if el.is_visible():
                            text = el.inner_text()
                            digits = re.sub(r'\D', '', text)
                            if digits and int(digits) > 100: # 100円以下は誤検知として無視
                                price = int(digits)
                                break

                    # --- 販売元チェック ---
                    # ログの「Amazon以外」という判定が正しいか検証するため、テキスト判定を緩和
                    is_official = False
                    buybox = page.locator("#buybox, #desktop_buybox, #rightCol").first
                    if buybox.is_visible():
                        bb_text = buybox.inner_text()
                        is_official = any(x in bb_text for x in ["Amazon.co.jp", "Amazonによる発送", "Amazon.co.jpが販売", "Amazon.co.jp directly"])

                    # --- 判定結果 ---
                    if price:
                        if is_official:
                            print(f"{item['name']}: 在庫あり判定 ({price}円)")
                            send_discord_notify(f"**【Amazon在庫あり】**\n{item['name']}\n価格: `{price}円`\n{item['url']}")
                        else:
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
