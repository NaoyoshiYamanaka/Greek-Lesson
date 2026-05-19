# Κοινή Drill — 聖書ギリシア語 習熟ドリル

研究員（山中尚義）個人用の、聖書ギリシア語パージング訓練アプリ。
Accordance などのツールで衰えがちな自力パースの感覚を、語形の形態的手掛かりを毎回言語化させることで再構築する設計。

## 主な機能

- 規則名詞（1〜3変化）・規則動詞（現在・未完了系の能動・中受 直説法）の認識ドリル
- 単独提示モード／節中提示モードの切替
- 答え合わせは正解時にも必ず開き、**語形の分解・手掛かり・類似形** を毎回表示
- SRS（間隔反復）と☆復習帳で間違えた語形を優先再出題
- iPhone Safari からホーム画面に追加 → PWA としてオフライン動作
- 進捗は localStorage に保存

## ファイル構成

```
index.html              # メインHTML（CSS インライン）
app.js                  # アプリロジック
sw.js                   # Service Worker（オフライン用）
manifest.json           # PWA マニフェスト
icon-180.png            # iOS ホーム画面用アイコン
icon-192.png / icon-512.png  # その他のサイズ
design.md               # MVP 設計書
data/
  questions.json        # 問題プール（1961 問）
  questions.json.js     # 同じ内容を window.QUESTIONS として公開
  glosses.json          # レマ → 日本語簡潔訳（Cowork の書き下ろし）
  glosses.json.js       # 同じ内容を window.GLOSSES として公開
scripts/
  build_question_pool.py  # MorphGNT/SBLGNT から問題プールを生成
  glosses.py              # 語義の元データ（Python 辞書）
  build_glosses.py        # glosses.py → data/glosses.json
```

## 語義の編集

`scripts/glosses.py` の `GLOSSES` 辞書を編集し、`python3 scripts/build_glosses.py` を実行すると `data/glosses.json` と `data/glosses.json.js` が再生成されます。MVP 初期版では出題量の約78%（957語中522語）に簡潔訳を付与済みで、残りは「（語義未登録）」と表示されます。出会ったら追記する運用です。

辞書（BDAG・織田・岩隈・Louw-Nida 等）の文言は転載していません。Cowork が一般的なNTギリシア語の知識から独自にパラフレーズした見出しです。違和感のあるものは直接編集してください。

## ローカルで試す

```bash
cd "Greek Lessons"
python3 -m http.server 8000
# → http://localhost:8000 をブラウザで開く
```

## デプロイ（GitHub Pages）

1. GitHub で公開リポジトリを作成（例：`koine-drill`）
2. このフォルダの中身を push
3. Settings → Pages → Source を `main` ブランチのルートに設定
4. 数分後、`https://<username>.github.io/koine-drill/` で公開される
5. iPhone Safari でアクセス → 共有メニュー → 「ホーム画面に追加」

## ライセンスとクレジット

- **本文**：[SBLGNT](http://sblgnt.com/) — Society of Biblical Literature Greek New Testament（SBLGNT EULA、非商用利用）
- **形態素タグ**：[MorphGNT](https://github.com/morphgnt/sblgnt) — CC BY-SA 3.0
- **アプリ本体**：山中尚義 個人用。第三者配布を目的としない。

著作物の取り扱いについて：辞書（BDAG、Louw-Nida、織田、岩隈、TDNT 等）および文法書（Wallace、BDF、Robertson 等）の本文・例文・定義文は **本アプリに一切転載していない**。パラダイム表・解説テキストは公知の文法事実のみを根拠に独自に書き下ろし。

## 問題プールの再生成

文法分類ロジックを変更する場合：

```bash
pip3 install py-sblgnt
python3 scripts/build_question_pool.py
# → data/questions.json と data/questions.json.js が再生成される
```
