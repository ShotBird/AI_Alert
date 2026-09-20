"""AI 커뮤니티 섹션: AI 이야기가 실제로 어디에서 '대화'되는가.

이 섹션은 두 번 갈아엎었다. 사용자 반응을 그대로 옮긴다.

1차(티켓 23 최초):
    "전체 순위가 애매하다. GeekNews 는 처음 들어본다. Threads 는 어디 있나?
     실제 '유저'들이 모여서 '대화 및 커뮤니티'를 구성하는 사이트를 의미한다."

2차(지금 이 파일):
    "AI 커뮤니티는 왜 죽어있는 Midjourney Discord같은게 추천되는건지.
     국내 커뮤니티는 아카라이브<< 로 도배되어있는데 이상해."

2차 반려의 원인은 **누적치를 활동으로 착각한 것**이었다. 디스코드 회원수는
"이 서버에 한 번이라도 들어온 사람"의 총합이라 서버가 죽어도 줄지 않는다.
아카라이브 구독자 수도 똑같이 누적이고, 심지어 죽은 채널에서는 0 으로
망가져 있었다. 그래서 이 파일의 규칙을 하나로 못 박는다.

    **누적치는 신호가 아니다. 시간 창(window) 안의 활동만 신호로 싣는다.**

측정 결과 (2026-09-21 실측, 전부 직접 호출해 확인):

- **디스코드는 접속자 수(presence)로 줄 세운다.**
  `GET https://discord.com/api/v10/invites/{code}?with_counts=true` 는
  `approximate_member_count`(누적 가입자)와 `approximate_presence_count`
  (지금 접속 중) 를 **둘 다** 준다. 전에는 앞엣것을 실었다. 이제 뒤엣것을
  싣고, 앞엣것은 비율과 함께 note 로만 내려보낸다. 사용자의 지적이 숫자로
  그대로 드러난다 — Midjourney 는 1,857만 명 중 4.2% 만 접속해 있고
  Claude(Anthropic) 는 12.8만 명 중 18.0%, AI HUB 는 25.8% 가 접속해 있다.
  초대 코드가 무효(HTTP 404 또는 `code: 10006`)면 그 서버는 목록에서 뺀다.

  **접속자 수의 한계도 적어 둔다.** presence 는 "지금 디스코드를 켜 둔 채 이
  서버에 들어와 있는 사람" 이지 "지금 말하고 있는 사람" 이 아니다. 자리비움도
  포함되고, 옛날에 한 번 들어왔다가 잊은 사람도 디스코드를 켜 두면 세어진다.
  그래서 큰 서버일수록 접속자 수에는 누적의 그림자가 남는다 — 대신 note 의
  비율(접속/누적)이 그 그림자를 드러낸다. Midjourney 4.2% 와 AI HUB 25.8%
  의 차이가 그것이다. 여기서 더 정확해지려면 서버 안의 메시지 수를 봐야 하고,
  그건 봇 초대와 권한이 필요해서 지금 우리가 가진 것으로는 못 한다.
- **아카라이브는 구독자 수를 버리고 글이 쌓이는 속도를 잰다.**
  채널 목록 페이지(`arca.live/b/{slug}`) 한 장에 공지가 아닌 글 30건 안팎이
  `<time datetime>` 과 댓글 수를 달고 들어 있다. 가장 새 글과 가장 오래된 글의
  시간 차로 "하루 글 수" 를 환산한다. 구독자 수를 버린 이유는 실측이 말해준다:

      채널          구독자     하루 글 수   최신 글
      /b/characterai  31,859      ~1,180    45분 전
      /b/aiart       106,988        ~260     2시간 전
      /b/aivideo       1,973           0    17일 전
      /b/novelai           0           0    2023-02-10
      /b/chatgpt           0           0    글 자체가 0건

  구독자 순으로는 aiart 가 characterai 를 3배 앞서지만, 실제로 대화가 오가는
  양은 characterai 가 4~5배 많다. 구독자 수는 순위를 거꾸로 알려주고 있었다.
- **구독자 0 행의 정체.** 파서가 고장난 게 아니었다. 아카라이브 페이지 HTML
  에 `구독자 0명` 이라고 **그렇게 적혀 있다**. `/b/chatgpt` 는 공지와 광고를
  빼면 글이 한 건도 없고, `/b/novelai` 는 마지막 글이 2023년 2월이다. 둘은
  목록에서 지웠다. `/b/aivideo` 는 2026-09-04 가 마지막이라 아래 7일 규칙에
  자동으로 걸려 빠지지만, 되살아나면 알아서 돌아오도록 목록에는 남겨둔다.
- **`discuss.pytorch.kr`(파이토치 한국 사용자 모임) 을 새로 넣었다.**
  Discourse 라서 `/about.json` 이 공개 통계를 그대로 준다 (실측:
  `posts_7_days` 86, `topics_7_days` 41, `active_users_7_days` 206).
  robots.txt 의 `User-agent: *` 는 `/admin/ /auth/ /session /search` 등만
  막고 `/about.json` 은 막지 않는다. 국내 AI 커뮤니티 중 아카라이브가 아니면서
  '대화가 오가고' + '읽어도 되는' 곳으로 실측 확인된 유일한 사이트다.

읽지 않기로 한 곳 (전부 직접 확인하고 내린 결론):

- **디시인사이드 — 영구 제외.** 이용약관이 비상업·개인 목적을 포함해 자동
  수집을 전면 금지한다. 스크레이퍼를 **만들지 않는다.** 갤러리 4개를 각각
  올리던 것을 한 줄로 합쳤다 — 못 재는 건 마찬가지인데 국내 칸만 채웠다.
- **레딧 — 비인증 경로가 아예 없다.** robots.txt 가 `User-agent: *` /
  `Disallow: /` 이고, Reddit Data API Wiki 는 "Clients must authenticate with
  a registered OAuth token" · "Traffic not using OAuth or login credentials
  will be blocked" 라고 못 박는다. 심지어 "Our robots.txt is for search
  engines, not Data API users" 라며 robots.txt 로 따질 문제도 아니라고 한다.
  무료 구간은 있지만(OAuth client 당 100 QPM) **앱 등록이 전제**다. 이슈 #3
  의 OAuth 신청이 여전히 유일한 합법 경로다.
- **Threads — 공식 API 에 길이 있으나 우리에겐 열쇠가 없다.** 공식 문서
  `developers.facebook.com/docs/threads/keyword-search` 에 `GET
  graph.threads.net/v1.0/keyword_search` 가 실재한다. 다만 같은 문서가
  "If your app has not been approved for the `threads_keyword_search`
  permission, the search will be performed only on posts owned by the
  authenticated user" 라고 적어 놓았다 — Meta 앱 심사를 통과하기 전에는 **내
  글만** 검색된다. 앱도 심사도 없으므로 오늘은 측정 불가가 맞다. robots.txt
  머리말도 "Collection of data on Threads through automated means is
  prohibited unless you have express written permission from Threads" 다.
  신청 절차는 티켓 보고서에 적어 사용자에게 넘긴다.
- **클리앙 AI당(`/service/board/cm_ai`) — 살아 있지 않다.** robots.txt 는
  `/service/board/` 를 허용하지만(쿼리스트링은 `Disallow: /*?*`), 목록 한
  장이 5개월치였다. 24시간 글 0건. "긁어도 되지만 잴 게 없다."
- **긱뉴스(news.hada.io) — 우리를 막는다.** robots.txt 는 허용적이지만
  `/new` 가 우리 UA 에 HTTP 403 을 돌려준다. 막힌 걸 우회하지 않는다.
- **X(트위터) · 디시인사이드 · 네이버 카페** — 순서대로 자동 수집 금지,
  약관 금지, 로그인 필수. 숫자 없이 사유만 싣는다.
- **버렸던 것 그대로**: GeekNews·velog·Zenn·Qiita·Kaggle·Stack Overflow·
  Lobsters — 대화 커뮤니티가 아니거나 robots.txt 가 우리를 뺀다.

디스코드 호출은 `budget.check("discord")`/`spend("discord")` 로 감싼다.
아카라이브·Discourse 는 돈이 드는 API 가 아니라 별도 예산 없이 호출 사이
간격만 둔다. 세 종류 다 결과를 `cache_path` 에 하루 캐시한다 — 캐시에는
`v` 키가 있고, 이 파일이 재는 대상을 바꾸면 `CACHE_VERSION` 을 올려서 옛
누적치가 새 라벨을 달고 되살아나는 일을 막는다.
"""

import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

from .budget import BudgetExceeded, BudgetUnavailable

UA = "ai-alert/0.1 (personal daily digest)"

DISCORD_API = "https://discord.com/api/v10/invites/{}?with_counts=true"
DISCORD_TIMEOUT = 15
DISCORD_PACING_SEC = 1.2  # 연속 호출을 막을 근거는 없지만 예의상 간격을 둔다

ARCA_BASE = "https://arca.live"
ARCA_TIMEOUT = 15
ARCA_PACING_SEC = 1.2
# 목록 한 줄. class 에 notice 가 들어간 줄은 공지·광고라 활동이 아니다.
ARCA_ROW_RE = re.compile(r'<a class="vrow column([^"]*)"[^>]*?href="([^"]*)"(.*?)</a>', re.S)
ARCA_TIME_RE = re.compile(r'<time[^>]*datetime="([^"]+)"')
ARCA_COMMENT_RE = re.compile(r'<span class="comment-count">\s*\[?(\d+)\]?')
# 마지막 글이 이보다 오래됐으면 커뮤니티가 아니다 — 목록에서 뺀다.
DEAD_AFTER_DAYS = 7

DISCOURSE_TIMEOUT = 15
DISCOURSE_PACING_SEC = 1.2

# 숫자든 아니든 하루 정도만 묵힌다 — 다음 실행에서 금방 다시 확인하도록.
CACHE_TTL_DAYS = 1
# 재는 대상이 바뀌면 올린다. 옛 캐시(회원수·구독자)가 새 라벨(지금 접속·
# 하루 글 수)을 달고 살아나는 사고를 막는 유일한 장치다.
CACHE_VERSION = 2

# AI 대화가 실제로 모이는 곳만 넣는다. kind 는 뭘로 잴지를 정한다:
#   "discord"    — Discord invite API 의 **접속자 수**(presence). 누적 회원수 아님.
#   "arca"       — 아카라이브 채널 목록에서 환산한 하루 글 수
#   "discourse"  — Discourse `/about.json` 의 최근 7일 글 수 → 하루 평균
#   "hn"         — collect.py 가 이미 모아 온 오늘자 HN 항목의 포인트 합
#   "unmeasured" — 잴 방법이 없다고 조사로 확인된 곳. 숫자 없이 이유만 붙는다.
#
# match 는 (도메인, 경로 접두사 또는 None, 쿼리 키 또는 None, 쿼리 값 또는 None)
# 튜플의 목록이다 — "화제 유입량"(mentions) 계산에서 이 커뮤니티를 가리키는
# 링크인지 판정할 때 쓴다. 디스코드처럼 도메인 하나를 여러 커뮤니티가 같이
# 쓰는 경우, 경로(초대 코드)까지 봐야 어느 서버를 가리키는지 구분된다.


def _discord(cid, name, code, note=None):
    """디스코드 항목 하나. 초대 코드가 곧 경로라 match 도 코드에서 만든다."""
    low = code.lower()
    return dict(id=cid, name=name, url=f"https://discord.gg/{code}",
                region="global", kind="discord", invite_code=code, blurb=note,
                match=(("discord.gg", "/" + low, None, None),
                       ("discord.com", "/invite/" + low, None, None)))


COMMUNITIES = [
    # 해외 — Discord ──────────────────────────────────────────────────────────
    # 전부 2026-09-21 에 초대 API 로 직접 확인했다. 접속자 수 기준으로 위에서부터
    # 나열해 뒀지만, 실제 순서는 매일 실측값이 정한다 — 이 목록 순서가 아니다.
    _discord("discord_midjourney", "Midjourney Discord", "midjourney"),
    _discord("discord_openai", "OpenAI Discord", "openai"),
    _discord("discord_suno", "Suno Discord", "suno"),
    _discord("discord_stablediffusion", "Stable Diffusion Discord", "stablediffusion"),
    # Anthropic 공식 서버. 이름이 'Claude' 라 화면에도 그렇게 적는다.
    _discord("discord_anthropic", "Claude Discord", "anthropic"),
    _discord("discord_ollama", "Ollama Discord", "ollama"),
    _discord("discord_nousresearch", "Nous Research Discord", "nousresearch"),
    # huggingface.co/join/discord 가 이 코드로 리다이렉트된다. 배너티 코드가
    # 아니라서 HF 쪽에서 새로 발급하면 바뀐다 — 그때는 404 로 잡혀 자동 제외된다.
    _discord("discord_huggingface", "Hugging Face Discord", "JfAtkvEtRb"),
    _discord("discord_civitai", "Civitai Discord", "civitai"),
    # NovelAI 본사(Anlatan) 공식 서버. 아카라이브 노벨AI 채널은 2023년에 멈췄지만
    # 본진은 접속률 24% 로 멀쩡히 살아 있다 — 누적치로 재면 안 보이던 곳이다.
    _discord("discord_novelai", "NovelAI Discord", "novelai"),
    _discord("discord_aihub", "AI HUB Discord", "aihub"),
    _discord("discord_openrouter", "OpenRouter Discord", "openrouter"),
    _discord("discord_eleutherai", "EleutherAI Discord", "eleutherai"),

    # 해외 — 그 외 ────────────────────────────────────────────────────────────
    dict(id="hn", name="Hacker News",
         url="https://news.ycombinator.com/", region="global",
         kind="hn",
         match=(("ycombinator.com", None, None, None),)),
    dict(id="reddit_localllama", name="Reddit r/LocalLLaMA",
         url="https://www.reddit.com/r/LocalLLaMA/", region="global",
         kind="unmeasured", reason=None,  # 아래에서 공통 사유를 채운다
         match=(("reddit.com", "/r/localllama", None, None),)),
    dict(id="reddit_machinelearning", name="Reddit r/MachineLearning",
         url="https://www.reddit.com/r/MachineLearning/", region="global",
         kind="unmeasured", reason=None,
         match=(("reddit.com", "/r/machinelearning", None, None),)),
    dict(id="reddit_stablediffusion", name="Reddit r/StableDiffusion",
         url="https://www.reddit.com/r/StableDiffusion/", region="global",
         kind="unmeasured", reason=None,
         match=(("reddit.com", "/r/stablediffusion", None, None),)),
    dict(id="reddit_chatgpt", name="Reddit r/ChatGPT",
         url="https://www.reddit.com/r/ChatGPT/", region="global",
         kind="unmeasured", reason=None,
         match=(("reddit.com", "/r/chatgpt", None, None),)),
    dict(id="reddit_artificial", name="Reddit r/artificial",
         url="https://www.reddit.com/r/artificial/", region="global",
         kind="unmeasured", reason=None,
         match=(("reddit.com", "/r/artificial", None, None),)),
    dict(id="threads", name="Threads",
         url="https://www.threads.com/", region="global",
         kind="unmeasured",
         reason="공식 API 의 keyword_search 는 Meta 앱 심사로 "
                "threads_keyword_search 권한을 받아야 남의 공개 글을 읽는다 "
                "(승인 전에는 내 글만 검색됨). 앱·심사가 아직 없다.",
         match=(("threads.com", None, None, None),
                ("threads.net", None, None, None))),
    dict(id="x", name="X(트위터)",
         url="https://x.com/", region="global",
         kind="unmeasured",
         # 2026-09-21 재확인: x.com/robots.txt 의 `User-agent: *` 는 통째로
         # `Disallow: /` 다. (전에 적어 뒀던 "AI 크롤러를 이름으로 지목한다"는
         # 사실과 달랐다 — x.com robots.txt 에 AI 크롤러 이름은 없다.
         # 이름이 있는 건 Googlebot·Bingbot 이고 그 둘만 예외로 열려 있다.)
         reason="robots.txt 의 User-agent: * 가 Disallow: / 다 — 이름을 받지 "
                "못한 수집기는 전 경로가 금지다.",
         match=(("x.com", None, None, None),
                ("twitter.com", None, None, None))),

    # 국내 ───────────────────────────────────────────────────────────────────
    # 아카라이브는 '살아 있는 채널만' 남긴다. /b/novelai(2023년 정지)와
    # /b/chatgpt(글 0건)는 목록에서 지웠고, /b/aivideo 는 7일 규칙이 매일
    # 판단한다 — 글이 다시 올라오면 스스로 돌아온다.
    dict(id="arca_characterai", name="아카라이브 캐릭터AI 채널",
         url="https://arca.live/b/characterai", region="kr",
         kind="arca", path="/b/characterai",
         match=(("arca.live", "/b/characterai", None, None),)),
    dict(id="arca_aiart", name="아카라이브 AI 그림 채널",
         url="https://arca.live/b/aiart", region="kr",
         kind="arca", path="/b/aiart",
         match=(("arca.live", "/b/aiart", None, None),)),
    dict(id="arca_aivideo", name="아카라이브 AI 영상 채널",
         url="https://arca.live/b/aivideo", region="kr",
         kind="arca", path="/b/aivideo",
         match=(("arca.live", "/b/aivideo", None, None),)),
    dict(id="pytorch_kr", name="파이토치 한국 사용자 모임",
         url="https://discuss.pytorch.kr/", region="kr",
         kind="discourse", api="https://discuss.pytorch.kr/about.json",
         match=(("pytorch.kr", None, None, None),)),

    # 국내 — 디시인사이드. 갤러리 4개를 한 줄로 합쳤다. 못 재는 것은 같은데
    # 네 줄이 국내 칸의 절반을 먹고 있었다. 스크레이퍼는 만들지 않는다.
    dict(id="dcinside_ai", name="디시인사이드 AI 갤러리",
         url="https://gall.dcinside.com/mgallery/board/lists?id=chatgpt",
         region="kr", kind="unmeasured",
         reason="이용약관이 비상업·개인 목적을 포함해 자동 수집을 전면 "
                "금지한다. 수집 코드를 만들지 않는다.",
         match=(("dcinside.com", "/mgallery/board/lists", "id", "chatgpt"),
                ("dcinside.com", "/mgallery/board/lists", "id", "midjourney"),
                ("dcinside.com", "/mgallery/board/lists", "id", "stablediffusion"),
                ("dcinside.com", "/mgallery/board/lists", "id", "aiart"))),
]

# 레딧 다섯 줄의 사유는 글자 하나까지 같다. 한 곳에서 채워 넣어 어긋날 일을 없앤다.
REDDIT_REASON = ("OAuth 앱 등록·토큰이 필수다. Reddit 문서가 "
                 "'Traffic not using OAuth will be blocked' 라고 못 박는다 "
                 "(robots.txt 도 Disallow: /). 이슈 #3 의 신청이 유일한 경로.")
for _c in COMMUNITIES:
    if _c["kind"] == "unmeasured" and _c.get("reason") is None:
        _c["reason"] = REDDIT_REASON
del _c


def _parts(url):
    """URL 에서 매칭용 (호스트, 경로, 쿼리) 를 뽑는다. 전부 소문자로 맞춘다."""
    try:
        sp = urlsplit((url or "").strip())
    except ValueError:
        return "", "", {}
    host = sp.netloc.lower()
    host = host.rsplit("@", 1)[-1].split(":", 1)[0].removeprefix("www.")
    path = (sp.path or "").lower()
    query = {k.lower(): v[0].lower() for k, v in parse_qs(sp.query).items() if v}
    return host, path, query


def _match(parts, community):
    """이 URL 이 이 커뮤니티를 가리키는가.

    도메인만 보지 않는다 — Discord 는 서버마다 도메인이 같고 초대 코드(경로)로만
    구분되고, 디시인사이드는 쿼리스트링의 갤러리 id 로만 구분된다.
    """
    host, path, query = parts
    if not host:
        return False
    for dom, prefix, qkey, qval in community["match"]:
        if host != dom and not host.endswith("." + dom):
            continue
        if prefix and not path.startswith(prefix):
            continue
        if qkey and query.get(qkey) != qval:
            continue
        return True
    return False


def _gravity(items):
    """화제 유입량 — 다른 곳에서 이 커뮤니티를 가리킨 횟수.

    **자기 피드의 자기 참조는 세지 않는다.** Hacker News 소스로 수집한 항목이
    news.ycombinator.com 을 가리키는 것은 "우리가 HN 을 몇 건 받았다"는 뜻이지
    "다른 곳에서 HN 화제가 몇 번 났다"는 뜻이 아니다. 우리 설정을 측정한 것이지
    세상을 측정한 게 아니다.
    """
    hits = {}
    for item in items:
        parts = _parts(item.get("url") or "")
        if not parts[0]:
            continue
        source = (item.get("source_name") or "").strip().lower()
        for com in COMMUNITIES:
            if not _match(parts, com):
                continue
            if source and source == com["name"].strip().lower():
                continue
            hits[com["id"]] = hits.get(com["id"], 0) + 1
    return hits


def _load_cache(path):
    # 캐시는 성능용이지 안전장치가 아니다(budget 과 다름) — 못 읽으면 빈 캐시로
    # 시작한다(fail-open). 캐시가 없다고 섹션이 멈출 이유는 없다.
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_cache(path, cache):
    try:
        parent = os.path.dirname(path) or "."
        os.makedirs(parent, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass  # 저장 실패도 이번 결과를 막을 이유가 아니다


def _cache_fresh(entry):
    """하루 안에 확인했고 **지금 재는 것과 같은 것을 잰** 캐시인가.

    버전을 같이 보는 이유: 누적 회원수를 담아 둔 옛 캐시가 '지금 접속' 이라는
    새 라벨을 달고 되살아나면, 고치려던 사고가 캐시를 통해 그대로 재현된다.
    """
    if entry.get("v") != CACHE_VERSION:
        return False
    checked = entry.get("checked_at")
    if not checked:
        return False
    try:
        checked_date = date.fromisoformat(checked)
    except ValueError:
        return False
    return (date.today() - checked_date).days < CACHE_TTL_DAYS


def _store(cache, cid, value, note, dropped=False):
    cache[cid] = dict(v=CACHE_VERSION, value=value, note=note, dropped=dropped,
                      checked_at=date.today().isoformat())


def _fetch_discord(code, budget, notes):
    """디스코드 초대 코드 하나를 조회한다.

    돌려주는 값은 (접속자 수 또는 None, 누적 회원수 또는 None, 상태, 사유)다.
    **앞의 것이 신호이고 뒤의 것은 맥락이다.** 순서를 바꾸지 말 것 — 예전에
    누적 회원수를 신호 자리에 놓아서 죽은 서버가 1위를 했다.

    상태는 "ok"/"error"/"invalid" 중 하나 — "invalid" 는 초대 코드 자체가
    죽었다는 뜻이라 호출부에서 그 서버를 목록에서 뺀다.
    """
    try:
        budget.check("discord")
    except BudgetExceeded:
        notes.append("discord 일일 호출 예산 도달 — 남은 서버 조회를 건너뜀")
        return None, None, "error", "예산 소진"
    except BudgetUnavailable as exc:
        notes.append(f"discord 호출 예산을 확인할 수 없음: {exc}")
        return None, None, "error", "예산 확인 불가"

    req = urllib.request.Request(
        DISCORD_API.format(code),
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=DISCORD_TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        budget.spend("discord")
        if exc.code == 404:
            # Unknown Invite — 코드가 무효화됐다. 재시도해도 살아나지 않는다.
            return None, None, "invalid", "초대 코드 무효(HTTP 404)"
        return None, None, "error", f"조회 실패(HTTP {exc.code})"
    except (urllib.error.URLError, socket.timeout) as exc:
        budget.spend("discord")
        return None, None, "error", f"조회 실패({type(exc).__name__})"
    budget.spend("discord")

    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None, None, "error", "응답 파싱 실패"

    if data.get("code") == 10006 or "approximate_member_count" not in data:
        return None, None, "invalid", "초대 코드 무효(Unknown Invite)"

    presence = data.get("approximate_presence_count")
    member = data.get("approximate_member_count")
    if presence is None:
        # with_counts=true 를 줬는데 접속자만 빠지는 경우는 못 봤지만,
        # 그렇다고 누적 회원수로 대신 채우지는 않는다 — 그게 이 티켓의 사고다.
        return None, member, "error", "접속자 수가 응답에 없음"
    return presence, member, "ok", None


def _arca_rows(html):
    """목록 HTML 에서 (작성시각, 댓글수) 를 뽑는다. 공지·광고 줄은 뺀다."""
    rows = []
    for cls, _href, body in ARCA_ROW_RE.findall(html):
        if "notice" in cls:
            continue  # 공지·광고는 채널 활동이 아니다
        t = ARCA_TIME_RE.search(body)
        if not t:
            continue
        try:
            when = datetime.fromisoformat(t.group(1).replace("Z", "+00:00"))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        c = ARCA_COMMENT_RE.search(body)
        rows.append((when, int(c.group(1)) if c else 0))
    return rows


def _fetch_arca(path, now=None):
    """아카라이브 채널의 **하루 글 수**를 잰다.

    돌려주는 값은 (하루 글 수 또는 None, note, 마지막 글 시각 또는 None).

    구독자 수를 쓰지 않는 이유는 모듈 docstring 에 있다 — 누적이고, 죽은
    채널에서는 0 으로 망가져 있으며, 순위를 거꾸로 알려준다.

    목록 한 장(공지 제외 30건 안팎)이 쌓이는 데 걸린 시간으로 속도를 낸다.
    바쁜 채널은 이 한 장이 한 시간도 안 되는 구간이라 24시간으로 **환산**한
    값이고, 새벽에는 느려지므로 낮에 재면 조금 높게 잡힌다. 그 사실을 감추지
    않으려고 note 에 원본 측정("최근 N건이 M분 만에 쌓임")을 같이 싣는다.
    """
    now = now or datetime.now(timezone.utc)
    req = urllib.request.Request(
        ARCA_BASE + path,
        headers={"User-Agent": UA, "Accept": "text/html"},
    )
    try:
        with urllib.request.urlopen(req, timeout=ARCA_TIMEOUT) as resp:
            raw = resp.read()
    except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout) as exc:
        return None, f"조회 실패({type(exc).__name__})", None

    rows = _arca_rows(raw.decode("utf-8", errors="replace"))
    if len(rows) < 2:
        # 글이 0~1건인 채널은 속도를 낼 수도 없고, 낼 필요도 없다.
        newest = rows[0][0] if rows else None
        return 0, "공지를 뺀 글이 사실상 없음", newest

    newest = max(r[0] for r in rows)
    oldest = min(r[0] for r in rows)
    span_h = (newest - oldest).total_seconds() / 3600
    # 0으로 나누는 것만 막는다. 실제로 걸릴 일은 없는 방어선이다.
    span_h = max(span_h, 0.1)
    # n건 사이의 간격은 n-1개다. n으로 나누면 속도가 살짝 부풀려진다.
    per_day = round((len(rows) - 1) / span_h * 24)

    comments = sum(c for _, c in rows)
    span_txt = (f"{span_h:.1f}시간" if span_h < 48
                else f"{span_h / 24:.0f}일")
    note = (f"최근 글 {len(rows)}건이 {span_txt} 만에 쌓인 속도 "
            f"· 그 글들에 달린 댓글 {comments:,}개")
    return per_day, note, newest


def _fetch_discourse(api_url):
    """Discourse 포럼의 공개 통계(`/about.json`)로 하루 글 수를 낸다.

    돌려주는 값은 (하루 글 수 또는 None, note, 마지막 활동 시각 또는 None).

    `posts_last_day` 를 그대로 쓰지 않는다 — 작은 포럼은 조용한 하루가 있고,
    그날의 0 이 "죽었다"로 읽히면 아카라이브 0 행과 같은 오해를 만든다.
    7일치를 7로 나눠 하루 평균을 내고, 원본 7일 수치를 note 에 남긴다.
    """
    req = urllib.request.Request(
        api_url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=DISCOURSE_TIMEOUT) as resp:
            raw = resp.read()
    except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout) as exc:
        return None, f"조회 실패({type(exc).__name__})", None
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None, "응답 파싱 실패", None

    stats = (data.get("about") or {}).get("stats") or {}
    posts7 = stats.get("posts_7_days")
    if posts7 is None:
        return None, "about.json 에 최근 7일 통계가 없음", None

    topics7 = stats.get("topics_7_days") or 0
    users7 = stats.get("active_users_7_days") or 0
    note = (f"최근 7일 글 {posts7:,}건의 하루 평균 "
            f"· 새 글타래 {topics7:,}개 · 활동 이용자 {users7:,}명")
    # posts_7_days 가 0이면 마지막 활동 시각을 '7일보다 전'으로 돌려 죽은 곳
    # 판정에 걸리게 한다. Discourse 는 마지막 글 시각을 직접 주지 않는다.
    now = datetime.now(timezone.utc)
    last = now if posts7 else now - timedelta(days=DEAD_AFTER_DAYS + 1)
    return round(posts7 / 7), note, last


def _row(c, signal_kind, signal_value, mentions, note):
    return dict(
        id=c["id"],
        name=c["name"],
        url=c["url"],
        # board.py 는 아직 row["domain"] 으로 `https://{domain}` 을 복원해 쓴다.
        # url 에서 스킴만 뗀 문자열을 넣으면 그 재구성이 그대로 맞는다.
        domain=c["url"].split("://", 1)[-1],
        region=c["region"],
        signal_kind=signal_kind,
        signal_value=signal_value,
        mentions=mentions,
        note=note,
    )


def top_communities(items, budget, cache_path, want=6):
    """AI 커뮤니티 행과 보드 notes 를 만든다.

    **누적치는 싣지 않는다.** 디스코드는 지금 접속 중인 사람 수, 아카라이브와
    Discourse 는 하루에 올라오는 글 수, HN 은 오늘 받은 포인트 합 — 전부 시간
    창 안의 활동이다. 누적 회원수·구독자 수는 서버가 죽어도 줄지 않아서
    "죽은 Midjourney 가 1위" 같은 결과를 만들었다. 그 숫자는 note 에만 남는다.

    **서로 다른 신호 종류를 하나의 순위로 합치지 않는다.** 지역별로 "숫자가
    있는 것부터, 있으면 값이 큰 순" 으로만 줄을 세운다. '지금 접속'과 '하루 글
    수'가 같은 줄에 있어도 그건 보기 편하라고 나열한 순서일 뿐, "이게 더
    크다"는 비교가 아니다 — 단위가 다르다.

    **활동이 멈춘 곳은 0 을 달고 남지 않고 빠진다.** 마지막 글이
    `DEAD_AFTER_DAYS` 보다 오래됐으면 커뮤니티가 아니다. 왜 빠졌는지는 notes
    에 남기고, 다시 글이 올라오면 다음 실행에서 스스로 돌아온다.

    `want` 는 지역마다 **신호 종류별로** 최대 몇 개까지 보여줄지 정한다.
    숫자가 없는("측정 불가") 곳은 이 상한과 무관하게 전부 나온다 — Threads
    가 몇 번째 줄에 있든, 사라지면 안 되는 게 이 섹션을 다시 만든 이유다.
    """
    notes = []
    gravity = _gravity(items)
    cache = _load_cache(cache_path)
    now = datetime.now(timezone.utc)

    made_discord_call = False
    made_web_call = False
    rows = []

    def cached(cid):
        entry = cache.get(cid)
        return entry if entry and _cache_fresh(entry) else None

    def pace():
        nonlocal made_web_call
        if made_web_call:
            time.sleep(max(ARCA_PACING_SEC, DISCOURSE_PACING_SEC))
        made_web_call = True

    for c in COMMUNITIES:
        mentions = gravity.get(c["id"], 0)
        kind = c["kind"]

        if kind == "discord":
            entry = cached(c["id"])
            if entry and entry.get("dropped"):
                notes.append(f"{c['name']}: {entry.get('note')} — 목록에서 제외 "
                             f"(마지막 확인 {entry['checked_at']})")
                continue
            if entry:
                value, note = entry.get("value"), entry.get("note")
            else:
                if made_discord_call:
                    time.sleep(DISCORD_PACING_SEC)
                presence, member, status, reason = _fetch_discord(
                    c["invite_code"], budget, notes)
                made_discord_call = True
                if status == "invalid":
                    _store(cache, c["id"], None, reason, dropped=True)
                    notes.append(f"{c['name']}: {reason} — 목록에서 제외")
                    continue
                value = presence
                if value is not None and member:
                    # 사용자가 지적한 바로 그 숫자를 여기에 둔다. 1,857만 명
                    # 중 4.2% 라는 사실이 '회원수 1,857만'보다 정직하다.
                    note = f"전체 회원 {member:,}명 중 {value / member * 100:.1f}% 접속"
                else:
                    note = reason or "접속자 수를 가져오지 못함"
                _store(cache, c["id"], value, note)
            rows.append(_row(c, "지금 접속", value, mentions, note))
            continue

        if kind in ("arca", "discourse"):
            entry = cached(c["id"])
            if entry and entry.get("dropped"):
                notes.append(f"{c['name']}: {entry.get('note')} — 목록에서 제외 "
                             f"(마지막 확인 {entry['checked_at']})")
                continue
            if entry:
                value, note = entry.get("value"), entry.get("note")
            else:
                pace()
                if kind == "arca":
                    value, note, last = _fetch_arca(c["path"], now=now)
                else:
                    value, note, last = _fetch_discourse(c["api"])
                # 조회에 성공했는데 마지막 활동이 오래됐다면 커뮤니티가 아니다.
                # 조회 실패(value is None)는 죽은 것과 다르다 — 내일 다시 본다.
                if value is not None and (
                        last is None or (now - last) > timedelta(days=DEAD_AFTER_DAYS)):
                    ago = f"{(now - last).days}일 전" if last else "알 수 없음"
                    dead = f"마지막 글이 {ago} — {DEAD_AFTER_DAYS}일 넘게 조용함"
                    _store(cache, c["id"], None, dead, dropped=True)
                    notes.append(f"{c['name']}: {dead} — 목록에서 제외")
                    continue
                _store(cache, c["id"], value, note)
            rows.append(_row(c, "하루 글 수", value, mentions, note))
            continue

        if kind == "hn":
            # 새로 부르지 않는다 — collect.py 가 오늘 이미 받아 온 HN 항목의
            # 포인트를 그대로 더한다. gravity 는 자기 참조를 빼지만, 여기서는
            # HN 자신의 오늘자 포인트를 재는 것이므로 자기 참조를 뺄 이유가
            # 없다 — 그래서 gravity 대신 직접 다시 매칭한다.
            today = [i for i in items if _match(_parts(i.get("url") or ""), c)]
            if not today:
                value, note = None, "오늘 HN 수집 항목이 없음"
            else:
                value = sum(i.get("engagement") or 0 for i in today)
                note = f"오늘 수집한 HN 항목 {len(today)}건의 포인트 합"
            rows.append(_row(c, "오늘 포인트 합", value, mentions, note))
            continue

        # kind == "unmeasured"
        rows.append(_row(c, "측정 불가", None, mentions, c["reason"]))

    _save_cache(cache_path, cache)

    picked = []
    for region in ("global", "kr"):
        rr = [r for r in rows if r["region"] == region]
        measured = [r for r in rr if r["signal_value"] is not None]
        unmeasured = sorted([r for r in rr if r["signal_value"] is None],
                            key=lambda r: (-r["mentions"], r["name"]))

        # want 는 신호 종류(signal_kind)마다 따로 적용한다 — 전체를 섞어서 자르면
        # HN의 "오늘 포인트 합"(대개 수백)이 디스코드 접속자 수(수만~수십만)에
        # 밀려 아예 안 보이게 된다. 그건 순위가 아니라 자릿수 차이일 뿐이라
        # 벤처가 통째로 빠질 이유가 못 된다. 종류별로 다 자른 뒤에야
        # 화면 표시용으로 값 기준 한 줄로 다시 정렬한다.
        by_kind = {}
        for r in measured:
            by_kind.setdefault(r["signal_kind"], []).append(r)
        kept = []
        for group in by_kind.values():
            group.sort(key=lambda r: (-r["signal_value"], r["name"]))
            kept.extend(group[:want])
        kept.sort(key=lambda r: (-r["signal_value"], r["name"]))

        picked.extend(kept)
        picked.extend(unmeasured)
    rows = picked

    if rows and all(r["signal_value"] is None for r in rows):
        notes.append("커뮤니티 신호를 하나도 못 가져옴 — 화제 유입량과 "
                     "측정 불가 사유만으로 목록을 채움")

    notes.append("커뮤니티 숫자는 전부 '지금/오늘'의 활동이다 — 디스코드는 접속 "
                 "중인 사람 수, 아카라이브·포럼은 하루 글 수, HN 은 오늘 포인트 "
                 "합. 누적 회원수·구독자 수는 서버가 죽어도 줄지 않아 쓰지 않는다 "
                 "(디스코드 누적 회원수는 비율과 함께 각 줄 설명에만 남긴다). "
                 "종류가 다른 숫자를 하나의 순위로 합치지 않는다.")

    notes = list(dict.fromkeys(notes))  # 같은 이유가 벤처마다 반복되면 중복만 없앤다

    return rows, notes


if __name__ == "__main__":
    # 실사용 Budget 은 실제 예산 파일에 쓰기 때문에, 여기서는 가짜 예산 객체로
    # 실제 Discord/arca.live/Discourse 호출이 이뤄지는지만 확인한다.
    import tempfile

    class _FakeBudget:
        def __init__(self):
            self.counts = {}

        def check(self, key, n=1):
            return 999

        def spend(self, key, n=1):
            self.counts[key] = self.counts.get(key, 0) + n

    fake_items = [
        dict(title="HN: 어떤 AI 글", url="https://news.ycombinator.com/item?id=1",
             source_name="Hacker News", engagement=120),
        dict(title="HN: 다른 AI 글", url="https://news.ycombinator.com/item?id=2",
             source_name="Hacker News", engagement=45),
        dict(title="미드저니 얘기가 나왔다", url="https://discord.gg/midjourney",
             source_name="TechCrunch", engagement=0),
        dict(title="아카라이브 AI 그림 채널 글", url="https://arca.live/b/aiart/999999",
             source_name="네이버 뉴스", engagement=0),
        dict(title="관계 없는 기사", url="https://example.com/foo",
             source_name="Example", engagement=0),
    ]

    cache_path = os.path.join(tempfile.gettempdir(), "ai_alert_community_verify_cache.json")
    if os.path.exists(cache_path):
        os.remove(cache_path)  # 매번 실제로 라이브 호출이 일어나는지 보려고 캐시를 지운다

    budget = _FakeBudget()
    rows, notes = top_communities(fake_items, budget, cache_path, want=6)

    print(f"=== 커뮤니티 {len(rows)}행 (호출 사용량: {budget.counts}) ===")
    for r in rows:
        val = f"{r['signal_value']:,}" if isinstance(r["signal_value"], int) else "—"
        print(f"[{r['region']:6}] {r['name']:26} {r['signal_kind']:10} {val:>10} "
              f"유입 {r['mentions']}  note={r['note']}")

    print("\n=== notes ===")
    for n in notes:
        print("-", n)

    # 검증 1: 측정 불가 행에는 숫자가 없다.
    bad = [r for r in rows if r["signal_value"] is not None and r["signal_kind"] == "측정 불가"]
    assert not bad, f"측정 불가인데 숫자가 붙은 행: {bad}"
    # 검증 2: 누적 회원수가 신호 자리에 오지 않았다. 이 티켓의 사고 그 자체다.
    #         디스코드 접속자 수가 누적 회원수와 같아지는 일은 현실에서 없다.
    for r in rows:
        if r["signal_kind"] == "지금 접속" and r["signal_value"] is not None:
            assert r["signal_value"] < 3_000_000, \
                f"접속자 수 자리에 누적 회원수가 들어온 듯하다: {r}"
    # 검증 3: 활동이 0인 행은 남아 있지 않다.
    zeros = [r for r in rows if r["signal_value"] == 0]
    assert not zeros, f"활동 0인데 목록에 남은 행: {zeros}"
    print("\n검증 통과: 측정 불가 행에 숫자 없음 · 신호 자리에 누적치 없음 · 0 행 없음.")
