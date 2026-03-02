# Azure Files Syncer
[![Build Windows Executable](https://github.com/kbt48/azurefiles-syncer/actions/workflows/build-windows.yml/badge.svg)](https://github.com/kbt48/azurefiles-syncer/actions/workflows/build-windows.yml)

Azure Files 上の指定ディレクトリを監視し、ローカルPCの指定ディレクトリへファイルを同期（ダウンロード）するツールです。動画ファイルなど、数百MB以上の大容量ファイルの同期を想定して設計されています。

## 主な仕様・挙動について

本ツールはファイル書き込み中の不完全なコピーを防ぎ、確実に同期を行うために以下のような仕様となっています。

### 1. 同期のトリガー（待機時間）
*   **定期スキャン (`scan_interval`)**: 
    設定された秒数ごとに、同期元（Azure Files）のフォルダ内を巡回し、新しいファイルや更新されたファイルがないか確認します。
*   **書き込み完了の判定 (`settle_time`)**: 
    ファイルが新しく見つかっても、すぐにはダウンロードを開始しません。
    ファイルサイズの変動が止まってから（＝書き込みが完了してから）、設定された `settle_time`（秒）が経過したことを確認して、初めてダウンロード処理を開始します。
    *   *例: `scan_interval=5`, `settle_time=5` の場合、書き込み完了から最低5秒、最大約10秒の待機時間が発生します。*

### 2. ダウンロード中の挙動（直列処理）
*   **単一ファイルの処理**: 
    1つのファイルのダウンロード（コピー）処理が始まると、**そのファイルのコピーが完全に終わるまで、他の処理（新規ファイルのスキャンや他のファイルのダウンロード）は一時停止（ブロック）されます。**
*   **複数ファイルが同時に配置された場合**: 
    複数のファイルが同時に同期条件を満たした場合でも、**見つかった順に1つずつ順番（直列）にダウンロード**されます。並列（同時）ダウンロードは行われません。

## 設定 (`config.toml`)
実行ファイルと同じ階層にある `config.toml` で動作を設定します。

```toml
[azure]
# Azure Storage アカウントの接続文字列（Azureポータルから取得）
connection_string = "DefaultEndpointsProtocol=https;AccountName=YOUR_ACCOUNT;AccountKey=YOUR_KEY;EndpointSuffix=core.windows.net"

# 同期対象のファイル共有名
share_name = "encoded-videos"

[sync]
# 共有内の監視対象ディレクトリ（ルートの場合は空文字 `""` または特定のパス `"some/folder"`）
source_dir = ""
target_dir = "C:\\SyncTarget"
scan_interval = 5

# ファイルサイズの変動が止まってから同期を開始するまでの待機時間（秒）
# 大きなファイルの書き込み途中での不完全なコピーを防ぐための「落ち着き時間」です。
settle_time = 5
```

## 開発環境
- Windows 11 / WSL2 (Ubuntu)
- Python 3.13
- パッケージ管理・ビルド: [uv](https://docs.astral.sh/uv/)

## ダウンロードとリリース

本ツールは GitHub Actions を用いて自動ビルドおよび自動リリースされるように構成されています。

### 最新版のダウンロード
1. GitHub リポジトリの **[Releases]** ページを開きます。
2. 最新のバージョン（例: `v1.0.0`）から `AzureFilesSyncer-Windows.zip` をダウンロードします。
3. ZIPファイルを解凍すると、実行ファイル（`.exe`）と設定ファイルのテンプレート（`config.example.toml`）が含まれています。

### 新しいバージョンのリリース手順（開発者向け）
ソースコードを更新して新しいバージョンを配布したい場合は、Gitでバージョンタグを打ってプッシュしてください。

```bash
# 変更をコミット
git add .
git commit -m "Update feature X"
git push origin main

# v1.0.0 というタグを作成してプッシュ
git tag v1.0.0
git push origin v1.0.0
```
タグ（`v...`）がプッシュされると、GitHub Actions が自動的に実行ファイルをビルド・ZIP化し、新しい Release として公開します。

## ビルド方法 (ローカル)
開発用に `uv` を使用してプロジェクトをローカルでビルドすることも可能です。

```bash
# 依存関係のインストール
uv sync

# 実行ファイル（.exe）のビルド
uv run pyinstaller --noconfirm --onefile --windowed --name "AzureFilesSyncer" syncer.py
```
ビルドが成功すると、`dist/` フォルダ内に `AzureFilesSyncer.exe` が生成されます。
