# Moto Archive 🏍️

<p align="center">
  <img src="https://img.shields.io/badge/Status-In--Development-orange" alt="Status">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Data-JSON-blue" alt="Data">
  <img src="https://img.shields.io/github/last-commit/raiton-boo/moto-archive" alt="Last Commit">
  <img src="https://img.shields.io/github/contributors/raiton-boo/moto-archive" alt="Contributors">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
</p>

日本が誇る誇る4大バイクメーカーを中心に、スペックなどのデータを集約・構造化するためのデータ収集プロジェクトです。
最終的には、あらゆるプラットフォームやアプリケーションで利用可能な「バイク情報の標準データベース」を目指しています。

## TL;DR

- 国内4メーカー（Honda, Kawasaki, Yamaha, Suzuki）のカタログスペックを集約するプロジェクト。
- 手動で収集した正確なデータをJSON形式で保存。
- 将来的にあらゆるSQLデータベースへエクスポート可能なパイプラインを構築予定。

## 目的

オートバイのカタログスペックを構造化データ（JSON）として蓄積し、アプリ開発や分析に自由に利用できる「バイク情報のデータベース」を目指します。

## データ収集について

現在は以下のリソースを参考に、**手動で** 丁寧にデータを収集・整形しています。

- 各メーカー公式サイト
- バイクブロス（BikeBros）

## 収集対象

現在は日本の4大メーカーを中心にデータを収集しています。

- **国内4メーカー**: Honda, Kawasaki, Yamaha, Suzuki
- **データ内容**: 排気量、最高出力、最大トルク、車体サイズ等のカタログスペック
- **今後の予定**: 海外メーカー（Ducati, BMW, KTM等）への拡大

## 技術仕様（予定）

- **データ管理**: JSON / JSONC
- **開発言語**: Python (データ処理・変換用)
- **対応予定DB**: PostgreSQL, MySQL, SQLite, Redis (いずれのうちどれか/または複数)

## 🤝 貢献について (Contributing)

データ提供やスキーマの改善案をお待ちしています！
具体的な仕様は以下を参照してください。

1. **ドキュメント**: [`docs/`](./docs/)
2. **データ構造定義**: [`data/schema.jsonc`](./data/schema.jsonc)

## ライセンス

このプロジェクトは [MIT License](LICENSE) の元で公開されています。
