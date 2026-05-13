<div id="top"></div>

# analysis-mlx-max-1

## 使用技術一覧

<p style="display: inline">
  <img src="https://img.shields.io/badge/-Python-3776AB.svg?logo=python&style=for-the-badge&logoColor=white">
  <img src="https://img.shields.io/badge/-Flask-000000.svg?logo=flask&style=for-the-badge">
  <img src="https://img.shields.io/badge/-Pandas-150458.svg?logo=pandas&style=for-the-badge">
  <img src="https://img.shields.io/badge/-scikit--learn-F7931E.svg?logo=scikit-learn&style=for-the-badge&logoColor=white">
  <img src="https://img.shields.io/badge/-Chart.js-FF6384.svg?logo=chartdotjs&style=for-the-badge&logoColor=white">
  <img src="https://img.shields.io/badge/-JavaScript-F7DF1E.svg?logo=javascript&style=for-the-badge&logoColor=black">
</p>

## 目次

1. [プロジェクトについて](#プロジェクトについて)
2. [環境](#環境)
3. [ディレクトリ構成](#ディレクトリ構成)
4. [主な機能](#主な機能)
5. [解析メニュー](#解析メニュー)
6. [時刻処理](#時刻処理)
7. [セットアップ](#セットアップ)
8. [注意事項](#注意事項)
10. [開発者情報](#開発者情報)

## プロジェクトについて

本プロジェクトは，MLX90632 による温度データと MAX30102 による心拍数データを，基準データおよび実験ログと照合し，タスクごとに評価するためのローカル Web 解析アプリケーションである．

主に，以下の評価を目的とする．

- MLX90632 の推定温度と体温データの比較
- 補正後 MLX データと体温データの比較
- MAX30102 による心拍数と ECG データの比較
- PPG 処理前後の心拍数データの比較
- アップロードした CSV / Excel ファイルの簡易プレビュー

評価結果として，有効データ数，MAE，RMSE，平均値などをタスク別に表示する．また，表示された結果は PNG 画像として保存できる．

<p align="right">(<a href="#top">トップへ</a>)</p>

## 環境

| カテゴリ | 項目 | 内容 |
| --- | --- | --- |
| **Backend** | 言語 / フレームワーク | Python / Flask |
| **Libraries** | 解析・統計 | Pandas, NumPy, scikit-learn |
| **Libraries** | Excel 読み込み | openpyxl |
| **Frontend** | 言語 / ライブラリ | HTML, CSS, JavaScript, Chart.js, html2canvas |
| **通信** | 方式 | Fetch API / CORS対応 |

<p align="right">(<a href="#top">トップへ</a>)</p>

## ディレクトリ構成

```text
.
├── app.py            # Flask バックエンド，解析処理，MAE / RMSE 算出
├── index.html        # ファイルアップロード画面，解析メニュー
├── script.js         # フロントエンド処理，結果表示，PNG 保存処理
├── style.css         # 画面デザイン，結果テーブルの装飾
├── requirements.txt  # Python ライブラリ一覧
└── README.md         # 本ファイル
```

<p align="right">(<a href="#top">トップへ</a>)</p>

## 主な機能

### 1. 解析メニューの選択実行

ファイルをアップロードし，実行したい解析メニューにチェックを入れることで，複数の解析を同時に実行できる．

現在の解析メニューは以下である．

- ファイル内容を表示
- MLX評価
- MAX評価
- MLX修正後評価

### 2. タスク別の評価

`log.csv` に含まれるタスク名と時刻を基に，実験データをタスク区間ごとに分割する．そのうえで，基準データとセンサデータを比較し，タスクごとの MAE，RMSE，有効データ数，平均値を算出する．

### 3. 柔軟な時刻パース

実験データに含まれる時刻形式の違いに対応するため，絶対時刻，Excel シリアル値，`分:秒` 形式，`時:分:秒` 形式などを変換する処理を備えている．

### 4. 結果の PNG 保存

解析結果として表示されたテーブル領域を，`html2canvas` により PNG 画像として保存できる．

<p align="right">(<a href="#top">トップへ</a>)</p>

## 解析メニュー

### ファイル内容を表示

アップロードしたファイルの内容を簡易的に表示する．

対応形式は以下である．

| 形式 | 表示内容 |
| --- | --- |
| `.csv` | 先頭 5 行の先頭列 |
| `.xlsx` / `.xls` | 各シートの先頭 5 行の先頭列 |

ファイルの中身やシート名を簡単に確認したい場合に使用する．

### MLX評価

MLX90632 の測定値と体温データを比較し，タスクごとに誤差を算出する．

#### 必要ファイル

| ファイル名 | 内容 |
| --- | --- |
| `log.csv` | 実験ログ，タスク名と時刻を含む |
| `body_temperature.csv` | 基準となる体温データ |
| `3-Device_Measurement.xlsx` | MLX90632 の測定データ |

#### 使用する主な情報

| ファイル | 使用内容 |
| --- | --- |
| `log.csv` | `Task_Name`，`Timestamp` |
| `body_temperature.csv` | 体温値，測定時刻 |
| `3-Device_Measurement.xlsx` | `Ambient_C`，`Object_C`，経過時間 |

#### 対応する MLX シート名

Excel ファイル内では，以下の順に MLX シートを探索する．

1. `MLX_L mini`
2. `MLX_L`
3. `MLX_R mini`
4. `MLX_R`

最初に見つかったシートを解析対象とする．

#### 出力内容

| 指標 | 内容 |
| --- | --- |
| 有効データペア数 | 体温データと MLX データを比較できた点数 |
| MAE | 平均絶対誤差 |
| RMSE | 二乗平均平方根誤差 |
| BodyTemp 平均 | タスク区間内の体温平均 |
| Object_C 平均 | タスク区間内の MLX 物体温度平均 |
| Ambient_C 平均 | タスク区間内の MLX センサ周辺温度平均 |

### MLX修正後評価

補正後の MLX データを体温データと比較する．通常の MLX評価とは異なり，Excel ではなく `mlx_re.csv` を使用する．

#### 必要ファイル

| ファイル名 | 内容 |
| --- | --- |
| `log.csv` | 実験ログ，タスク名と時刻を含む |
| `body_temperature.csv` | 基準となる体温データ |
| `mlx_re.csv` | 補正後 MLX データ |

#### 使用する主な列

| 列 | 内容 |
| --- | --- |
| A列 | `Ambient_C` |
| E列 | `SensorElapsed_ms` |
| F列 | `MeasureElapsed_s` |
| I列 | `TO_Final_Corrected` |

`TO_Final_Corrected` を補正後の `Object_C` として扱い，体温データとの MAE / RMSE を算出する．

#### 出力内容

通常の MLX評価と同様に，タスクごとの有効データ数，MAE，RMSE，平均値を表示する．

### MAX評価

MAX30102 から得られた心拍数データを，ECG データおよび処理後 PPG データと比較する．

#### 必要ファイル

| ファイル名 | 内容 |
| --- | --- |
| `ecg.csv` | ECG による基準心拍数 |
| `PPG_BPM.csv` | MAX30102 由来の心拍数 |
| `PPG_fin_BPM.csv` | 処理後または比較用の PPG 心拍数 |
| `log.csv` | 実験ログ，タスク名と時刻を含む |

#### 使用する主な列

| ファイル | 使用列 |
| --- | --- |
| `ecg.csv` | `Timestamp`，`HeartRate_BPM` |
| `PPG_BPM.csv` | `RecvJST`，`HR_BPM` |
| `PPG_fin_BPM.csv` | `RecvJST`，`HR_BPM` |
| `log.csv` | `Task_Name`，`Timestamp` |

#### 比較内容

| 比較 | 内容 |
| --- | --- |
| ECG vs PPG_BPM | ECG を基準として，MAX30102 の心拍数を評価 |
| PPG_fin vs PPG_BPM | 処理後 PPG と元の PPG_BPM を比較 |

#### 出力内容

タスクごとに，以下の2条件で MAE / RMSE を表示する．

| 条件 | 内容 |
| --- | --- |
| 元データ | 元の時系列データを用いた評価 |
| 1分平均 | 1分ごとに平均化したデータを用いた評価 |

<p align="right">(<a href="#top">トップへ</a>)</p>

## 時刻処理

本アプリでは，実験データに含まれる時刻形式の違いに対応するため，独自の時刻パーサを使用している．

対応する主な形式は以下である．

- 日付付き絶対時刻
- 日付なし時刻
- Excel シリアル値
- `分:秒`
- `時:分:秒`
- 小数秒を含む経過時間

MLX評価では，`BLE_START_TIME (Main)` を基準時刻として，センサ側の経過時間を加算することで測定時刻を復元する．その後，体温データの時刻に合わせて MLX データを時間補間し，誤差を算出する．

<p align="right">(<a href="#top">トップへ</a>)</p>

## セットアップ

### 1. 仮想環境の作成

```bash
python -m venv .venv
```

Windows の場合は，以下で仮想環境を有効化する．

```bash
.venv\Scripts\activate
```

macOS / Linux の場合は，以下で仮想環境を有効化する．

```bash
source .venv/bin/activate
```

### 2. 必要ライブラリのインストール

```bash
pip install -r requirements.txt
```

### 3. Flask サーバの起動

```bash
python app.py
```

サーバは以下の URL で起動する．

```text
http://127.0.0.1:5000
```

### 4. アプリの起動

`index.html` をブラウザで開く．

フロントエンドは，アップロードされたファイルを `http://127.0.0.1:5000/upload` に送信する．そのため，先に Flask サーバを起動しておく必要がある．

<p align="right">(<a href="#top">トップへ</a>)</p>

## 注意事項

このアプリは旧解析アプリであり，現在の実験形式に完全対応しているとは限らない．特に以下の点に注意する．

- 必要ファイル名が固定されている．
- 一部の列位置が固定されている．
- タスク名がコード内に直接記述されている．
- 入力ファイルの形式が変わると解析できない場合がある．
- 時刻同期の確認用グラフは現状では実装されていない．
- Chart.js は読み込まれているが，現在の主な結果表示はテーブル形式である．

<p align="right">(<a href="#top">トップへ</a>)</p>

## 開発者情報

Name: Takato Ishii

Portfolio: https://takato-ishii.vercel.app/

<p align="right">(<a href="#top">トップへ</a>)</p>