"""AI 커뮤니티 섹션: AI 이야기가 실제로 어디에서 '대화'되는가.

이 섹션은 한 번 잘못 만들어져서 통째로 다시 짰다. 사용자 반응을 그대로 옮긴다:

    "전체 순위가 애매하다. GeekNews 는 처음 들어본다. Threads 는 어디 있나?
     실제 '유저'들이 모여서 '대화 및 커뮤니티'를 구성하는 사이트를 의미한다."

원래 목록(ticket 23 조사 결과)에는 뉴스 수집기(GeekNews), 블로그 호스팅(velog·Zenn·
Qiita), 대회 플랫폼(Kaggle) 이 섞여 있었다 — 전부 '대화가 모이는 곳'이 아니다.
게다가 전부를 Tranco 글로벌 순위 하나로 줄 세웠는데, reddit.com 의 글로벌 순위는
레딧 **전체**의 규모이지 AI 대화가 오가는 서브레딧의 규모가 아니다. 이 섹션에서는
그래서 **Tranco 를 완전히 들어낸다.** 대신 커뮤니티마다 잴 수 있는 실제 신호를
직접 붙인다 — 신호의 '종류'가 다르면 숫자도 다른 것을 재는 것이므로 하나의
순위로 합치지 않는다(디스코드 회원수와 아카라이브 구독자는 단위가 다르다).

확인된 사실 (구현 근거, ticket 23 에서 직접 호출해 확인):

- **디스코드 초대 코드는 인증 없이 회원수를 준다.**
  `GET https://discord.com/api/v10/invites/{code}?with_counts=true` 가
  `approximate_member_count`/`approximate_presence_count` 를 돌려준다.
  실측(예시): Midjourney 18,571,398명/754,499명 온라인, OpenAI 857,034명,
  Hugging Face 238,396명, Stable Diffusion 321,583명, Learn AI Together
  101,774명, EleutherAI 39,417명. 초대 코드가 무효(Unknown Invite, HTTP 404
  또는 `code: 10006`)가 되면 그 서버는 **목록에서 뺀다** — 옛 코드로 죽은 숫자를
  들고 있는 것보다 빠지는 게 정직하다.
- **아카라이브는 채널 페이지에 구독자 수를 그대로 적어 놓는다.**
  (`arca.live/b/aiart` 페이지 HTML 에 "구독자 106,988명"처럼 박혀 있다.)
  robots.txt 가 허용적이라 긁어도 된다.
- **레딧은 비로그인으로 아무것도 안 준다.** `about.json`·`old.reddit.com`·
  `widgets.json` 전부 403. robots.txt 는 `Disallow: /`. 페이지도 클라이언트
  렌더링이라 HTML 안에 숫자가 없다. 그래서 AI 서브레딧들은 **숫자 없이** 벤처
  자체만 올린다 — 긁지 않고, 지어내지 않는다.
- **Threads 와 X(트위터) 는 아무것도 안 준다.** 둘 다 robots.txt 가 자동 수집을
  명시적으로 금지하고 AI 크롤러를 이름으로 지목한다. 그래도 Threads 는 반드시
  나와야 한다 — 사용자가 "어디 갔냐"고 직접 물은 자리다. '측정 불가'라고 이름
  붙여서 그대로 보여준다.
- **디시인사이드 AI 갤러리는 존재는 한다** (`chatgpt`·`midjourney`·
  `stablediffusion`·`aiart` 마이너 갤러리, 200 OK) **하지만 못 잰다.**
  robots.txt 가 이름 붙은 AI 크롤러를 차단하고, 애초에 '구독자' 개념이 없다
  (갤러리는 추천수만 있다).
- **Hacker News 는 `collect.py` 가 이미 Algolia API 로 실어 온다.** 항목마다
  `engagement`(포인트)가 붙어 있으니 새로 부를 필요 없이 오늘 수집분을 그대로
  합산한다.
- **버렸다**: GeekNews·velog·Zenn·Qiita·Kaggle·Stack Overflow — 대화 커뮤니티가
  아니다. **Lobsters 도 버렸다** — `hottest.json` 자체는 열리지만 robots.txt 의
  `User-agent: *` 가 우리 UA 를 포함해 `Disallow: /` 이므로(화이트리스트에 든
  건 Bing·Google 같은 이름 붙은 크롤러뿐) 긁을 권한이 없다. "잴 수 있으면 남긴다"
  는 조건 자체가 성립하지 않는다.

디스코드 호출은 `budget.check("discord")`/`spend("discord")` 로 감싼다 (LIMITS 에
`discord` 키가 아직 없으면 `BudgetUnavailable` 이 나는데, 그러면 그 서버는 회원수
없이 이유만 달고 나온다 — 죽지 않는다). 아카라이브는 돈이 드는 API 가 아니라
별도 예산 없이 호출 사이 간격만 둔다. 두 종류 다 결과를 `cache_path` 에 하루
정도 캐시해서 매 실행마다 다시 긁지 않는다.
"""

import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from datetime import date
from urllib.parse import parse_qs, urlsplit

from .budget import BudgetExceeded, BudgetUnavailable

UA = "ai-alert/0.1 (personal daily digest)"

DISCORD_API = "https://discord.com/api/v10/invites/{}?with_counts=true"
DISCORD_TIMEOUT = 15
DISCORD_PACING_SEC = 1.2  # 연속 호출을 막을 근거는 없지만 예의상 간격을 둔다

ARCA_BASE = "https://arca.live"
ARCA_TIMEOUT = 15
ARCA_PACING_SEC = 1.2
# 페이지 HTML 에 그대로 박혀 있는 "구독자 106,988명" 형태를 뽑는다.
ARCA_SUB_RE = re.compile(r"구독자\s*([\d,]+)\s*명")

# 숫자든 아니든 하루 정도만 묵힌다 — 다음 실행에서 금방 다시 확인하도록.
CACHE_TTL_DAYS = 1

# AI 대화가 실제로 모이는 곳만 넣는다. kind 는 뭘로 잴지를 정한다:
#   "discord"    — Discord invite API 로 회원수/온라인 수
#   "arca"       — 아카라이브 채널 페이지의 구독자 수
#   "hn"         — collect.py 가 이미 모아 온 오늘자 HN 항목의 포인트 합
#   "unmeasured" — 잴 방법이 없다고 조사로 확인된 곳. 숫자 없이 이유만 붙는다.
#
# match 는 (도메인, 경로 접두사 또는 None, 쿼리 키 또는 None, 쿼리 값 또는 None)
# 튜플의 목록이다 — "화제 유입량"(mentions) 계산에서 이 커뮤니티를 가리키는
# 링크인지 판정할 때 쓴다. 디스코드처럼 도메인 하나를 여러 커뮤니티가 같이
# 쓰는 경우, 경로(초대 코드)까지 봐야 어느 서버를 가리키는지 구분된다.
COMMUNITIES = [
    # 해외 — Discord ──────────────────────────────────────────────────────────
    dict(id="discord_midjourney", name="Midjourney Discord",
         url="https://discord.gg/midjourney", region="global",
         kind="discord", invite_code="midjourney",
         match=(("discord.gg", "/midjourney", None, None),
                ("discord.com", "/invite/midjourney", None, None))),
    dict(id="discord_openai", name="OpenAI Discord",
         url="https://discord.gg/openai", region="global",
         kind="discord", invite_code="openai",
         match=(("discord.gg", "/openai", None, None),
                ("discord.com", "/invite/openai", None, None))),
    dict(id="discord_stablediffusion", name="Stable Diffusion Discord",
         url="https://discord.gg/stablediffusion", region="global",
         kind="discord", invite_code="stablediffusion",
         match=(("discord.gg", "/stablediffusion", None, None),
                ("discord.com", "/invite/stablediffusion", None, None))),
    dict(id="discord_huggingface", name="Hugging Face Discord",
         url="https://discord.gg/JfAtkvEtRb", region="global",
         # huggingface.co/join/discord 가 지금 이 코드로 리다이렉트된다(확인함).
         # 배너티(vanity) 코드가 아니라서 HF 쪽에서 새로 발급하면 바뀔 수 있다 —
         # 그때는 404(Unknown Invite)로 잡혀 자동으로 목록에서 빠진다.
         kind="discord", invite_code="JfAtkvEtRb",
         match=(("discord.gg", "/JfAtkvEtRb".lower(), None, None),
                ("discord.com", "/invite/JfAtkvEtRb".lower(), None, None))),
    dict(id="discord_learnaitogether", name="Learn AI Together Discord",
         url="https://discord.gg/learnaitogether", region="global",
         kind="discord", invite_code="learnaitogether",
         match=(("discord.gg", "/learnaitogether", None, None),
                ("discord.com", "/invite/learnaitogether", None, None))),
    dict(id="discord_eleutherai", name="EleutherAI Discord",
         url="https://discord.gg/eleutherai", region="global",
         kind="discord", invite_code="eleutherai",
         match=(("discord.gg", "/eleutherai", None, None),
                ("discord.com", "/invite/eleutherai", None, None))),

    # 해외 — 그 외 ────────────────────────────────────────────────────────────
    dict(id="hn", name="Hacker News",
         url="https://news.ycombinator.com/", region="global",
         kind="hn",
         match=(("ycombinator.com", None, None, None),)),
    dict(id="reddit_localllama", name="Reddit r/LocalLLaMA",
         url="https://www.reddit.com/r/LocalLLaMA/", region="global",
         kind="unmeasured",
         reason="레딧은 비로그인 조회가 전부 403 이고 robots.txt 가 "
                "Disallow: / 다. 숫자를 긁지 않는다.",
         match=(("reddit.com", "/r/localllama", None, None),)),
    dict(id="reddit_machinelearning", name="Reddit r/MachineLearning",
         url="https://www.reddit.com/r/MachineLearning/", region="global",
         kind="unmeasured",
         reason="레딧은 비로그인 조회가 전부 403 이고 robots.txt 가 "
                "Disallow: / 다. 숫자를 긁지 않는다.",
         match=(("reddit.com", "/r/machinelearning", None, None),)),
    dict(id="reddit_stablediffusion", name="Reddit r/StableDiffusion",
         url="https://www.reddit.com/r/StableDiffusion/", region="global",
         kind="unmeasured",
         reason="레딧은 비로그인 조회가 전부 403 이고 robots.txt 가 "
                "Disallow: / 다. 숫자를 긁지 않는다.",
         match=(("reddit.com", "/r/stablediffusion", None, None),)),
    dict(id="reddit_chatgpt", name="Reddit r/ChatGPT",
         url="https://www.reddit.com/r/ChatGPT/", region="global",
         kind="unmeasured",
         reason="레딧은 비로그인 조회가 전부 403 이고 robots.txt 가 "
                "Disallow: / 다. 숫자를 긁지 않는다.",
         match=(("reddit.com", "/r/chatgpt", None, None),)),
    dict(id="reddit_artificial", name="Reddit r/artificial",
         url="https://www.reddit.com/r/artificial/", region="global",
         kind="unmeasured",
         reason="레딧은 비로그인 조회가 전부 403 이고 robots.txt 가 "
                "Disallow: / 다. 숫자를 긁지 않는다.",
         match=(("reddit.com", "/r/artificial", None, None),)),
    dict(id="threads", name="Threads",
         url="https://www.threads.com/", region="global",
         kind="unmeasured",
         reason="robots.txt 가 자동 수집을 명시적으로 금지하고 AI 크롤러를 "
                "이름으로 지목한다.",
         match=(("threads.com", None, None, None),
                ("threads.net", None, None, None))),
    dict(id="x", name="X(트위터)",
         url="https://x.com/", region="global",
         kind="unmeasured",
         reason="robots.txt 가 자동 수집을 명시적으로 금지하고 AI 크롤러를 "
                "이름으로 지목한다.",
         match=(("x.com", None, None, None),
                ("twitter.com", None, None, None))),

    # 국내 — 아카라이브 (구독자 수 스크랩 가능) ─────────────────────────────────
    dict(id="arca_aiart", name="아카라이브 AI 그림 채널",
         url="https://arca.live/b/aiart", region="kr",
         kind="arca", path="/b/aiart",
         match=(("arca.live", "/b/aiart", None, None),)),
    dict(id="arca_chatgpt", name="아카라이브 챗지피티 채널",
         url="https://arca.live/b/chatgpt", region="kr",
         kind="arca", path="/b/chatgpt",
         match=(("arca.live", "/b/chatgpt", None, None),)),
    dict(id="arca_characterai", name="아카라이브 캐릭터AI 채널",
         url="https://arca.live/b/characterai", region="kr",
         kind="arca", path="/b/characterai",
         match=(("arca.live", "/b/characterai", None, None),)),
    dict(id="arca_aivideo", name="아카라이브 AI 영상 채널",
         url="https://arca.live/b/aivideo", region="kr",
         kind="arca", path="/b/aivideo",
         match=(("arca.live", "/b/aivideo", None, None),)),
    dict(id="arca_novelai", name="아카라이브 노벨AI 채널",
         url="https://arca.live/b/novelai", region="kr",
         kind="arca", path="/b/novelai",
         match=(("arca.live", "/b/novelai", None, None),)),

    # 국내 — 디시인사이드 (존재는 하지만 못 잰다) ────────────────────────────────
    dict(id="dc_chatgpt", name="디시인사이드 챗지피티 갤러리",
         url="https://gall.dcinside.com/mgallery/board/lists?id=chatgpt",
         region="kr", kind="unmeasured",
         reason="robots.txt 가 이름 붙은 AI 크롤러를 차단하고, '구독자' 개념이 "
                "없다(추천수만 있음).",
         match=(("dcinside.com", "/mgallery/board/lists", "id", "chatgpt"),)),
    dict(id="dc_midjourney", name="디시인사이드 미드저니 갤러리",
         url="https://gall.dcinside.com/mgallery/board/lists?id=midjourney",
         region="kr", kind="unmeasured",
         reason="robots.txt 가 이름 붙은 AI 크롤러를 차단하고, '구독자' 개념이 "
                "없다(추천수만 있음).",
         match=(("dcinside.com", "/mgallery/board/lists", "id", "midjourney"),)),
    dict(id="dc_stablediffusion", name="디시인사이드 스테이블디퓨전 갤러리",
         url="https://gall.dcinside.com/mgallery/board/lists?id=stablediffusion",
         region="kr", kind="unmeasured",
         reason="robots.txt 가 이름 붙은 AI 크롤러를 차단하고, '구독자' 개념이 "
                "없다(추천수만 있음).",
         match=(("dcinside.com", "/mgallery/board/lists", "id", "stablediffusion"),)),
    dict(id="dc_aiart", name="디시인사이드 AI 그림 갤러리",
         url="https://gall.dcinside.com/mgallery/board/lists?id=aiart",
         region="kr", kind="unmeasured",
         reason="robots.txt 가 이름 붙은 AI 크롤러를 차단하고, '구독자' 개념이 "
                "없다(추천수만 있음).",
         match=(("dcinside.com", "/mgallery/board/lists", "id", "aiart"),)),
]


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
    checked = entry.get("checked_at")
    if not checked:
        return False
    try:
        checked_date = date.fromisoformat(checked)
    except ValueError:
        return False
    return (date.today() - checked_date).days < CACHE_TTL_DAYS


def _fetch_discord(code, budget, notes):
    """디스코드 초대 코드 하나를 조회한다.

    돌려주는 값은 (회원수 또는 None, 온라인수 또는 None, 상태, 사유)다.
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

    return (data.get("approximate_member_count"),
            data.get("approximate_presence_count"), "ok", None)


def _fetch_arca(path):
    """아카라이브 채널 페이지에서 "구독자 N명" 을 긁는다. (숫자 또는 None, 사유)."""
    req = urllib.request.Request(
        ARCA_BASE + path,
        headers={"User-Agent": UA, "Accept": "text/html"},
    )
    try:
        with urllib.request.urlopen(req, timeout=ARCA_TIMEOUT) as resp:
            raw = resp.read()
    except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout) as exc:
        return None, f"조회 실패({type(exc).__name__})"

    html = raw.decode("utf-8", errors="replace")
    m = ARCA_SUB_RE.search(html)
    if not m:
        return None, "페이지에서 구독자 수를 찾지 못함"
    try:
        return int(m.group(1).replace(",", "")), None
    except ValueError:
        return None, "구독자 수 파싱 실패"


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

    Tranco 글로벌 순위는 이 섹션에서 완전히 빠졌다 — 사이트 전체 규모는 AI
    대화의 크기와 무관하다는 게 이전 조사의 결론이다. 대신 커뮤니티마다
    실제로 잴 수 있는 신호(디스코드 회원수, 아카라이브 구독자, HN 포인트)를
    직접 붙이고, 잴 수 없는 곳(레딧·Threads·X·디시인사이드)은 그 사실을
    "측정 불가" 로 그대로 보여준다 — 조용히 빼지 않는다.

    **서로 다른 신호 종류를 하나의 순위로 합치지 않는다.** 지역별로 "숫자가
    있는 것부터, 있으면 값이 큰 순" 으로만 줄을 세운다. 디스코드 회원수와
    아카라이브 구독자가 같은 줄에 있어도 그건 보기 편하라고 나열한 순서일
    뿐, "이게 더 크다"는 비교가 아니다 — 단위가 다르다.

    `want` 는 지역마다 숫자가 있는 벤처를 최대 몇 개까지 보여줄지 정한다.
    숫자가 없는("측정 불가") 벤처는 이 상한과 무관하게 전부 나온다 — Threads
    가 몇 번째 줄에 있든, 사라지면 안 되는 게 이 섹션을 다시 만든 이유다.
    """
    notes = []
    gravity = _gravity(items)
    cache = _load_cache(cache_path)

    made_discord_call = False
    made_arca_call = False
    rows = []

    for c in COMMUNITIES:
        mentions = gravity.get(c["id"], 0)
        kind = c["kind"]

        if kind == "discord":
            entry = cache.get(c["id"])
            if entry and entry.get("dropped") and _cache_fresh(entry):
                notes.append(f"{c['name']}: {entry.get('note')} — 목록에서 제외 "
                             f"(마지막 확인 {entry['checked_at']})")
                continue
            if entry and _cache_fresh(entry) and not entry.get("dropped"):
                value, note = entry.get("value"), entry.get("note")
            else:
                if made_discord_call:
                    time.sleep(DISCORD_PACING_SEC)
                member, online, status, reason = _fetch_discord(
                    c["invite_code"], budget, notes)
                made_discord_call = True
                if status == "invalid":
                    cache[c["id"]] = dict(value=None, note=reason, dropped=True,
                                          checked_at=date.today().isoformat())
                    notes.append(f"{c['name']}: {reason} — 목록에서 제외")
                    continue
                value = member
                note = (f"온라인 {online:,}명" if value is not None and online
                        else reason)
                cache[c["id"]] = dict(value=value, note=note, dropped=False,
                                      checked_at=date.today().isoformat())
            rows.append(_row(c, "회원수", value, mentions, note))
            continue

        if kind == "arca":
            entry = cache.get(c["id"])
            if entry and _cache_fresh(entry):
                value, note = entry.get("value"), entry.get("note")
            else:
                if made_arca_call:
                    time.sleep(ARCA_PACING_SEC)
                value, note = _fetch_arca(c["path"])
                made_arca_call = True
                cache[c["id"]] = dict(value=value, note=note,
                                      checked_at=date.today().isoformat())
            rows.append(_row(c, "구독자", value, mentions, note))
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

    def region_rows(region):
        return [r for r in rows if r["region"] == region]

    picked = []
    for region in ("global", "kr"):
        rr = region_rows(region)
        measured = [r for r in rr if r["signal_value"] is not None]
        unmeasured = sorted([r for r in rr if r["signal_value"] is None],
                            key=lambda r: (-r["mentions"], r["name"]))

        # want 는 신호 종류(signal_kind)마다 따로 적용한다 — 전체를 섞어서 자르면
        # HN의 "오늘 포인트 합"(대개 수백)이 디스코드 회원수(수십만~수백만)에
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

    notes.append("커뮤니티마다 신호의 종류(회원수·구독자·오늘 포인트 합)가 다르다 — "
                 "숫자가 있는 곳부터 값 기준으로 나열하되, 종류가 다른 숫자를 "
                 "하나의 순위로 합치지 않는다. 숫자가 없는 곳은 '측정 불가' 사유와 "
                 "함께 그대로 남긴다.")

    notes = list(dict.fromkeys(notes))  # 같은 이유가 벤처마다 반복되면 중복만 없앤다

    return rows, notes


if __name__ == "__main__":
    # 실사용 Budget 은 LIMITS 에 아직 "discord" 키가 없어서 BudgetUnavailable 로
    # 막힌다(그 키는 이 파일을 쓰는 쪽에서 곧 추가하기로 했다) — 그래서 여기서는
    # 진짜 Budget 대신 가짜 예산 객체를 써서 실제 Discord/arca.live 호출이
    # 이뤄지는지를 확인한다. 총 호출 수: discord 6 + arca 5 = 11 (< 15).
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
        print(f"[{r['region']:6}] {r['name']:28} {r['signal_kind']:10} {val:>12} "
              f"유입 {r['mentions']}  note={r['note']}")

    print("\n=== notes ===")
    for n in notes:
        print("-", n)

    # 검증: 숫자를 실제로 가져오지 않은 행은 signal_value 가 None 이어야 한다
    # (측정 불가 벤처, 또는 이번 실행에서 조회가 실패한 벤처).
    bad = [r for r in rows if r["signal_value"] is not None and r["signal_kind"] == "측정 불가"]
    assert not bad, f"측정 불가인데 숫자가 붙은 행: {bad}"
    print("\n검증 통과: 측정 불가 행에는 숫자가 없다.")
