# Azure Files Syncer
[![Build Windows Executable](https://github.com/kbt48/azurefiles-syncer/actions/workflows/build-windows.yml/badge.svg)](https://github.com/kbt48/azurefiles-syncer/actions/workflows/build-windows.yml)

Azure Files 上の指定ディレクトリを監視しローカルPCの指定ディレクトリへファイルを同期（ダウンロード）するツール

動画ファイルなど数百MB以上の大容量ファイルの同期を想定して設計されている。

## 主な仕様・挙動について

本ツールはファイル書き込み中の不完全なコピーを防ぎ、確実に同期を行うために以下のような仕様となっている。

### 1. 同期のトリガー（待機時間）
*   **定期スキャン (`scan_interval`)**: 
    設定された秒数ごとに同期元（Azure Files）のフォルダ内を巡回し新しいファイルや更新されたファイルがないか確認する。
*   **書き込み完了の判定 (`settle_time`)**: 
    ファイルが新しく見つかってもすぐにはダウンロードを開始しない。
    ファイルサイズの変動が止まってから（＝書き込みが完了してから）設定された `settle_time`（秒）が経過したことを確認して初めてダウンロード処理を開始する。
    *   *例: `scan_interval=5` `settle_time=5` の場合書き込み完了から最低5秒 最大約10秒の待機時間が発生する。*

### 2. ダウンロード中の挙動（直列処理）
*   **単一ファイルの処理**: 
    1つのファイルのダウンロード（コピー）処理が始まると**そのファイルのコピーが完全に終わるまで他の処理（新規ファイルのスキャンや他のファイルのダウンロード）は一時停止（ブロック）される。**
*   **複数ファイルが同時に配置された場合**: 
    複数のファイルが同時に同期条件を満たした場合でも**見つかった順に1つずつ順番（直列）にダウンロード**される。並列（同時）ダウンロードは行われない。

## 設定 (`config.toml`)
実行ファイルと同じ階層にある `config.toml` で動作を設定する。

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
# 大きなファイルの書き込み途中での不完全なコピーを防ぐための「落ち着き時間」
settle_time = 5
```

## 開発環境
- Windows 11 / WSL2 (Ubuntu)
- Python 3.13
- パッケージ管理・ビルド: [uv](https://docs.astral.sh/uv/)

## ダウンロードとリリース

本ツールは GitHub Actions を用いて自動ビルドおよび自動リリースされるように構成されている。

### 最新版のダウンロード
1. GitHub リポジトリの **[Releases]** ページを開く。
2. 最新のバージョン（例: `v1.0.0`）から `AzureFilesSyncer-Windows.zip` をダウンロードする。
3. ZIPファイルを解凍すると実行ファイル（`.exe`）と設定ファイルのテンプレート（`config.example.toml`）が含まれている。

### 新しいバージョンのリリース手順（開発者向け）
ソースコードを更新して新しいバージョンを配布したい場合はGitでバージョンタグを打ってプッシュする。

```bash
# 変更をコミット
git add .
git commit -m "Update feature X"
git push origin main

# v1.0.0 というタグを作成してプッシュ
git tag v1.0.0
git push origin v1.0.0
```
タグ（`v...`）がプッシュされるとGitHub Actions が自動的に実行ファイルをビルド・ZIP化し新しい Release として公開する。

## ビルド方法 (ローカル)
開発用に `uv` を使用してプロジェクトをローカルでビルドすることも可能である。

```bash
# 依存関係のインストール
uv sync

# 実行ファイル（.exe）のビルド
uv run pyinstaller --noconfirm --onefile --windowed --name "AzureFilesSyncer" syncer.py
```
ビルドが成功すると `dist/` フォルダ内に `AzureFilesSyncer.exe` が生成される。
