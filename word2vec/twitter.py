import oauthlib.oauth1
import urllib, json

# @<img>{twitter-api}で確認したAPI Keyを入力
oauth_client = oauthlib.oauth1.Client(
    client_key='Consumer Key (API Key)',
    client_secret='Consumer Secret (API Secret)',
    resource_owner_key = 'Access Token',
    resource_owner_secret = 'Access Token Secret'
)

def getrecource(method, url, body=None):
    """
    Twitter APIをたたく為の汎用関数
    method: HTTP Method、'GET'もしくは'POST'になると思う。
    url: APIのエンドポイントURI
    body: APIに渡すパラメータ、型はdict
    """
    global oauth_client

    if body is not None:
        body = urllib.parse.urlencode(body)
        if method == 'GET':
            url += "?" + body
            body = None

    # OAuth認証情報を付与
    uri, headers, body = oauth_client.sign(
        url,
        http_method=method,
        headers = {
            'Content-Type' : 'application/x-www-form-urlencoded'
        } if method=='POST' else None,
        body=body
    )

    req = urllib.request.Request(
        uri,
        headers=headers,
        data=body.encode() if body is not None else None,
        method=method
    )

    with urllib.request.urlopen(req) as res:
        raw = res.read()
    if res.headers['Content-Type'] == 'application/json;charset=utf-8':
        return json.loads(raw.decode())
    else:
        return raw

def tweet_of_user(screen_name, include_rts=True, trim_user=True, count=1000):
    """
    ユーザを指定してTweetを取得する。

    screen_name: ユーザのScreen Name
    include_rts: Retweetを含むか
    trim_user: ユーザ情報を含むか
    count: 取得Tweet上限 (max 1000)
    """
    maxid = None
    tweets = []
    for i in range(5):
        data = getrecource(
            'GET',
            'https://api.twitter.com/1.1/statuses/user_timeline.json',
            dict(
                screen_name=screen_name,
                include_rts=1 if include_rts else 0,
                count=min(200, count - len(tweets)),
                trim_user=1 if trim_user else 0
                **({'max_id': maxid} if maxid is not None else {})
            )
        )
        if len(data) == 0:
            break
        maxid = int(data[-1]['id'])-1
        tweets += data
        if len(tweets) >= count:
            break
    return tweets[:count]

def get_sample_tweet(count=None, filterfunc=None):
    """
    ランダムサンプリングされたTweetを返す。iteratorを返す。
    時間帯にもよるが日本語Tweetは秒数個程度。
    cout=Noneだとエラーが怒らない限り無限に取得する。
    繋ぎっぱなしだと時々エラーで落ちるので、その処理は別途必要。

    count: 最大取得数
    filterfunc: Tweetに対するフィルタ。
                lambda tw:tw.get('lang') == 'ja' とか。
    """
    global oauth_client
    url = 'https://stream.twitter.com/1.1/statuses/sample.json'

    # OAuth認証情報を付与
    uri, headers, body = oauth_client.sign(
        url,
        http_method="GET",
    )

    req = urllib.request.Request(
        uri,
        headers=headers,
        method="GET"
    )

    raw = []

    with urllib.request.urlopen(req) as res:
        while count is None or count>0:
            r = res.read(1024)

            # TweetはJSONの改行区切りで渡されるため、改行があったらパースする。
            if b'\r\n' in r:
                lines = (b''.join(raw) + r).split(b'\r\n')
                for l in lines[:-1]:
                    tw = json.loads(l.decode())

                    # filterfuncが指定されていて、Falseを返したらそのTweetは捨てる。
                    if filterfunc is not None and not filterfunc(tw):
                        continue

                    # count が指定されていたら、デクリメントしていき0になったらbreak
                    if count is not None:
                        count -= 1
                        if count == 0:
                            break

                    yield tw

                raw = lines[-1:]

            # 改行がない場合は積んでおく
            else:
                raw.append(r)

    #Connection を閉じてから yield
    yield json.loads(l.decode())
