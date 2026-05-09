# Playwright公式のPython環境を使用（ブラウザインストール済み）
FROM mcr.microsoft.com/playwright/python:v1.59.0-jammy

# 作業ディレクトリの設定
WORKDIR /app

# 依存ライブラリのインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードのコピー
COPY . .

# ポートの設定
ENV PORT=10000
EXPOSE 10000

# 実行コマンド
CMD ["python", "main.py"]
