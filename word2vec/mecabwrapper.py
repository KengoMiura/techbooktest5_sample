import MeCab, csv, io, pandas as pd

parser = MeCab.Tagger("-Ochasen")

def parseText(text):
    """
    textを単語に分解し、[入力,読み,原型,品詞,活用,活用形]を列とするDataFrameを返す。
    """
    global parser
    with io.StringIO(parser.parse(text)) as fp:

        # MeCab.Tagger.parse の出力は "-Ochasen"のとき
        # タブ区切りテキストで返されるのでそれをパースする。
        r = csv.reader(fp, delimiter='\t')

        return pd.DataFrame(
            # 最終行は "[EOF]"なので無視
            list(r)[:-1],
            columns=['入力','読み','原型','品詞','活用','活用形']
        )
