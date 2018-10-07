# Word2Vecで遊ぶサンプル

## ファイル
* sample.ipynb: 本体。Jupyter Notebookで上から順に実行してください。
* tweetanalysis.py: 再利用する関数を定義しておいたファイル。
* twitter.py, mecabwrapper.py: Twitter、Mecabを扱う簡易ライブラリ。
* word_expectation.db: 集計済み単語カウント。

##　使用法
1. 本文の通り必要モジュールをインストールする。
1. 学習済みモデルを準備。
1. Twitter API Keyを取得 [LINK](https://apps.twitter.com/)
1. 一式を同じフォルダにいれ、Jupyter Notebookでsample.ipynbを実行
	1. API Keyやユーザー名等***になっているところは埋めてください。
