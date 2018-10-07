import mecabwrapper,twitter
import pandas.core
import regex
pandas.core.strings.re = regex

#@range_begin(tools)
import numpy as np
def normalize(a, axis=None):
    norm = np.linalg.norm(a, axis=axis)
    if len(norm.shape) == len(a.shape):
        return a / norm
    else:
        return a / norm.reshape(norm.shape[:axis] + (1,) + norm.shape[axis:])
def cos_similarity(a,b):
    return (normalize(a)*normalize(b)).sum()
#@range_end(tools)

#@range_begin(filter_tweet)
#Botではないクライアント
client_whitelist = {
  'Twitter for iPhone', 'Twitter for Android', 'Twitter Web Client',  'Twitter Lite',
  'Twitter for iPad', 'TweetDeck', 'feather for iOS', 'Janetter', 'Tween', 'twicca'}

import re, regex
def filter_tweet(tw):
    """
    意味のなさそうなTweetを除外する。

    returns: bool
    """
    if (
        #日本語ではない
        tw.get('lang') != 'ja'

        #リツイートである
        or tw.get('retweeted_status')

        #ハッシュタグを含む
        or len(tw['entities']['hashtags'])

        #twitter.com以外のURLを含む
        or not all(
            map(lambda x: x['display_url'].startswith('twitter.com/'),
                tw['entities']['urls']
               )
        )
    ):
        return False

    #Tweetソースがホワイトリストになければ除外
    m = re.search(
        'href="(?P<source_url>https?://(?P<source_domain>[^/]+).*?)"'
        ' rel.*?>\s*(?P<source_name>.*?)\s*<',
        tw.get('source')
    )
    if not m or m.group('source_name') in client_whitelist:
        return False

    #同一文字の5以上の連続または平仮名・カタカナ以外の2文字以上の連続の5回出現
    if regex.search(
        r'(.)\1{4}|([^\p{Hiragana}\p{Katakana}]+)(?:.*\2){4}',
        tw['text']
    ):
        return False

    return True
#@range_end(filter_tweet)

#@range_begin(filter_words)
#pandas の正規表現をregexモジュールに変更
import pandas.core
import regex
pandas.core.strings.re = regex

def filter_words(df):
    """
    意味のなさそうな単語を除外する。
    """
    return df.loc[
        lambda x: (

            #特定の品詞を除外
            ~x['品詞'].str.match('記号|.*非自立|助動?詞|接続詞|.*接尾|.*接頭')

            # 記号や数字ではない"普通の"文字を含んでいる。
            & x['原型'].str.match('[\p{Ll}\p{Lo}\p{Lu}\p{Lt}]')

            #平仮名・カタカナ・アルファベットの1文字は除外
            & (
                (x['原型'].str.len()>1)
                | ~x['原型'].str.match('[\p{Hiragana}\p{Katakana}a-zA-Z]')
            )
        )
    ]
#@range_end(filter_words)

#@range_begin(parse_tweet)
import re, regex, unicodedata
import pandas as pd, scipy.stats as stats
def parse_tweet(text):
    """
    Tweetをいい感じに正規化して単語のリストを返す。

    text: Tweetの本文

    returns: DataFrame
    """

    #記号、URL、ハッシュタグ、引用部分を除去し、文字を正規化
    text = unicodedata.normalize(
            'NFKC',
            regex.sub(
                # 引用符等の記号、空白文字
                '[\'",＂“”〝〟、，’‘＇]|\s+'
                # RT、ハッシュタグ、ユーザー、URL
                '|RT\s*([@#]\w+\s*)?:.*|[@#]\w+|https?://[\w/\.…]+',
                ' ',
                text
            )
        )

    # 空白以外の文字が5文字以下、もしくは仮名・漢字が全体の7割以下の場合は
    # 真っ当な日本語の文ではないと判定
    if (
        len(re.findall('\S', text)) <= 5
        or (
            len(regex.findall('[\p{Kana}\p{Han}\p{Hiragana}ー]', text)) /
            len(re.findall('\S', text)) <= 0.7
        )
    ):
        #そのまま結合可能なように空のDataFrameを返す。
        return pd.DataFrame()

    #それ以外の際は単語リストを返す。
    return mecabwrapper.parseText(
        text
    )

def parse_tweet_list(tweets):
    """
    Twitter APIから返されたJSONをdictしたデータの
    listを順次パースする。

    tweets: list of dict

    returns: generator of DataFrame
    """
    for tw in tweets:
        df = parse_tweet(tw['text'])
        if len(df) > 0:
            yield df

def get_tweets_score(screen_name, expectation, model):
    """
    ユーザーの単語出現数をカウントし、Poisson分布に基づく情報量Scoreを計算する。

    screen_name: Twitterのユーザー名
    expectation: 単語の標準的な出現頻度についてのDataFrame
    """
    tws = twitter.tweet_of_user(screen_name)
    words = [*parse_tweet_list(tws)]

    N = len(words)
    df = filter_words(
        pd.concat(words)
    )['原型'].value_counts().to_frame('N')

    expectation_min = expectation['expectation'].min()

    return df.loc[
        lambda x:x.index.map(model.__contains__)
    ].join(
        expectation * N
    ).fillna({

        # これまで集計に出てこなかった単語については、
        # 0にするとinfになるため、最小の単語の半分とする。
        'expectation': expectation_min*N/2
    }).assign(
        score=lambda x:-np.log2(
            stats.poisson.sf(
                x['N'],
                x['expectation']
            )

        # 倍精度浮動小数点数の関係上log2は-1024未満にならないはず
        # 実際試してみると何故か多少異なるがこのくらいで切っておく
        ).clip(min=-1023)
    ), N
#@range_end(parse_tweet)

#@range_begin(get_feature_vector)
def get_feature_vector(words_score, model):
    """
        単語の特徴量ベクトルの重み付き和を計算する。

        words_score: 単語の重みのDataFrame
        model: gensim.models.Word2Vec

        return: 特徴量ベクトル
    """

    vec = np.zeros(model.vector_size)
    for k, r in words_score.iterrows():
        if k in model.wv:
            # 一旦正規化して (絶対値で割って)からスコアをかけて足している。
            vec += model.wv[k] / np.linalg.norm(model.wv[k]) * r['score']
    return vec
#@range_end(get_feature_vector)

#@range_begin(orthogonal_words)
def orthogonal_words(v, model, topn=10):
    """
    most_similarに近いが、単語一つ選択した後に
    それに直交する成分のみを用いて次を選択していく

    v: ndarray 特徴量ベクトル (v.size==model.wv.vector_size)
    model: gensim.models.Word2Vec
    topn: int 出力する単語数

    returns list of (word, cosign similarity)
    """
    W = np.zeros((model.vector_size, topn))
    words = []
    v1  = v

    for i in range(topn):
        [(word, similarity)] = model.most_similar([v1], topn=1)

        W[:, i] = model.wv[word]
        words.append((word,similarity))

        q,r = np.linalg.qr(W[:,:i+1])

        v1 = v - np.einsum('i,ij,kj->k', v, q, q)

    return words
#@range_end(orthogonal_words)
