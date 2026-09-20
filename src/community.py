"""AI 커뮤니티 Top5 섹션: AI 이야기가 실제로 어디에 모이는가.

정직하게 밝히는 것부터: 사이트 하나의 **전체** 트래픽 순위는 AI 화제의 양을 말해주지
않는다. reddit.com 의 글로벌 순위는 레딧 전체의 규모이지 r/LocalLLaMA 의 규모가 아니다.
게다가 Threads·디시인사이드 같은 곳은 자동 수집(스크래핑)을 약관으로 금지한다.
그래서 "AI 전용 트래픽"은 아예 잴 수 없다. 이 섹션은 대신 합법적으로 잴 수 있는
둘을 분리해서 보여주고, 어느 쪽이 어느 뜻인지 그대로 밝힌다.

1. **화제 유입량 (discussion gravity)** — 오늘 이미 수집한 항목(Item) 중 몇 개가
   이 커뮤니티 도메인을 가리키는가. AI 화제에 대한 신호이고, 이미 공짜로 가진 데이터다.
2. **전체 트래픽 순위 (global rank)** — Tranco 의 글로벌 랭크. AI 특화 지표가 **아니라**
   그 사이트 전체 규모다. 그래서 빼지 않고 "이건 전체 규모다" 라고 이름 그대로 보여준다.

확인된 사실 (구현 근거):
- `GET https://tranco-list.eu/api/ranks/domain/{domain}` 은 무료·무인증이다.
  `{"ranks":[{"date":"2026-09-19","rank":615}, ...], "domain":"..."}` 형태로 온다.
  threads.com -> 615, dcinside.com -> 1205 로 실제 확인했다.
  목록에 없는 도메인은 `{"ranks": [], "domain": ...}` 처럼 빈 배열로 온다
  (news.ycombinator.com 이 그랬다) — 이건 오류가 아니라 "미등재"로 다룬다.
- **연속으로 빠르게 부르면 HTTP 429 를 HTML 바디로 돌려준다.** 그래서 호출 사이에
  최소 간격을 두고, 한 번 실행에 몇 번까지 부를지 `want` 로 자연히 제한하고,
  결과를 로컬 JSON 캐시에 며칠 단위로 저장한다 (랭킹은 하루에 1 정도만 움직이므로
  며칠 묵혀도 된다). 429 나 HTML 응답은 예외로 죽이지 않고 "순위 모름"으로 넘긴다.
- Hacker News Algolia(`https://hn.algolia.com/api/v1/search`)는 `collect.py` 가 이미
  쓰는 무료 API 다. hit 에는 `url`, `points`, `num_comments`, `created_at` 이 있다.

Tranco 예산(`budget.check("tranco")`/`spend("tranco")`)이 바닥나거나 Tranco 자체가
아예 응답하지 않아도 이 섹션은 죽지 않는다 — 화제 유입량만으로 순위를 매기고,
전체 트래픽 순위가 비었다는 사실을 notes 에 남긴다.
"""

import json
import os
import socket
import time
import urllib.error
import urllib.request
from datetime import date
from urllib.parse import urlsplit

from .budget import BudgetExceeded, BudgetUnavailable

UA = "ai-alert/0.1 (personal daily digest)"
TRANCO_API = "https://tranco-list.eu/api/ranks/domain/{}"
TRANCO_TIMEOUT = 15
# 연속 호출이 429 로 튕기는 걸 확인했다. 호출 사이 최소 간격을 둔다.
TRANCO_PACING_SEC = 1.5
# 랭킹은 하루에 1 정도만 움직인다. 성공한 조회는 며칠 묵혀 써도 된다.
CACHE_TTL_DAYS = 5
# 실패(요청 제한·오류)는 짧게만 묵힌다 — 다음 실행에서 금방 다시 시도하도록.
FAIL_TTL_DAYS = 1

# AI 대화가 모일 법한 커뮤니티 후보. 스크랩 가능 여부와 무관하게 넣는다 —
# 못 긁는 곳(Threads, 디시인사이드 등)의 규모를 보여주는 것도 이 섹션의 목적이다.
# aliases 는 같은 커뮤니티가 쓰는 다른 도메인이다 (화제 유입량 매칭에만 쓰고,
# Tranco 조회는 domain 하나로만 한다).
COMMUNITIES = [
    # 해외 ────────────────────────────────────────────────────────────────────
    dict(domain="huggingface.co", name="Hugging Face", region="global",
         aliases=["hf.co"]),
    dict(domain="reddit.com", name="Reddit", region="global", aliases=["old.reddit.com"]),
    dict(domain="news.ycombinator.com", name="Hacker News", region="global",
         aliases=["ycombinator.com"]),
    dict(domain="x.com", name="X(트위터)", region="global", aliases=["twitter.com"]),
    dict(domain="threads.com", name="Threads", region="global", aliases=["threads.net"]),
    dict(domain="discord.com", name="Discord", region="global", aliases=["discord.gg"]),
    dict(domain="lobste.rs", name="Lobsters", region="global"),
    dict(domain="kaggle.com", name="Kaggle", region="global"),
    dict(domain="zenn.dev", name="Zenn", region="global"),
    dict(domain="qiita.com", name="Qiita", region="global"),

    # 국내 ────────────────────────────────────────────────────────────────────
    # 국내는 후보 자체가 적다. 해외와 같은 표에 섞으면 규모에 밀려 한 곳도 안 보인다.
    dict(domain="news.hada.io", name="GeekNews", region="kr", aliases=["hada.io"]),
    dict(domain="arca.live", name="아카라이브", region="kr"),
    dict(domain="dcinside.com", name="디시인사이드", region="kr",
         aliases=["gall.dcinside.com"]),
    dict(domain="clien.net", name="클리앙", region="kr"),
    dict(domain="velog.io", name="velog", region="kr"),
    dict(domain="okky.kr", name="OKKY", region="kr"),
]


def _domain(url):
    """URL 에서 매칭용 호스트를 뽑는다. www. 는 떼고, 포트/계정정보는 버린다."""
    try:
        host = urlsplit((url or "").strip()).netloc.lower()
    except ValueError:
        return ""
    host = host.rsplit("@", 1)[-1].split(":", 1)[0]
    return host.removeprefix("www.")


def _match(host, community):
    if not host:
        return False
    for dom in (community["domain"],) + tuple(community.get("aliases", ())):
        if host == dom or host.endswith("." + dom):
            return True
    return False


def _gravity(items):
    """화제 유입량 — 다른 곳에서 이 커뮤니티를 가리킨 횟수.

    **자기 피드의 자기 참조는 세지 않는다.** 그걸 세면 GeekNews 가 50건이 되는데,
    그건 GeekNews 에서 AI 이야기가 50번 벌어졌다는 뜻이 아니라
    우리가 GeekNews RSS 를 50건 받았다는 뜻이다. 우리 설정을 측정한 것이지
    세상을 측정한 게 아니다.

    남는 것은 진짜 교차 참조뿐이라 숫자가 작고 대개 0 이다. 그게 정직한 값이다.
    """
    hits = {}
    for item in items:
        host = _domain(item.get("url") or "")
        if not host:
            continue
        source = (item.get("source_name") or "").strip()
        for com in COMMUNITIES:
            if not _match(host, com):
                continue
            # 이 항목을 가져온 곳이 곧 그 커뮤니티라면 자기 참조다
            if source and source.lower() == com["name"].lower():
                continue
            row = hits.setdefault(com["domain"], {"mentions": 0, "engagement": 0})
            row["mentions"] += 1
            row["engagement"] += (item.get("engagement") or 0)
    return hits


def _load_cache(path):
    # 캐시는 성능용이지 안전장치가 아니다(budget 과 다름) — 못 읽으면 그냥 빈 캐시로
    # 시작한다(fail-open). 매번 새로 긁는 것보다야 낫지만, 캐시가 없다고 섹션이
    # 멈출 이유는 없다.
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
        pass  # 저장 실패도 이번 순위표를 막을 이유가 아니다


def _cache_fresh(entry):
    checked = entry.get("checked_at")
    if not checked:
        return False
    try:
        checked_date = date.fromisoformat(checked)
    except ValueError:
        return False
    ttl = CACHE_TTL_DAYS if entry.get("rank") is not None else FAIL_TTL_DAYS
    return (date.today() - checked_date).days < ttl


def _fetch_rank(domain, budget, notes):
    """Tranco 글로벌 랭크 하나를 조회한다. 실패해도 예외를 던지지 않고 (None, 이유)."""
    try:
        budget.check("tranco")
    except BudgetExceeded:
        notes.append("tranco 일일 호출 예산 도달 — 남은 순위 조회를 건너뜀")
        return None, "예산 소진"
    except BudgetUnavailable as exc:
        notes.append(f"tranco 호출 예산을 확인할 수 없음: {exc}")
        return None, "예산 확인 불가"

    req = urllib.request.Request(
        TRANCO_API.format(domain),
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TRANCO_TIMEOUT) as resp:
            raw = resp.read()
            ctype = resp.headers.get("Content-Type", "") or ""
    except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout) as exc:
        budget.spend("tranco")
        return None, f"조회 실패({type(exc).__name__})"
    budget.spend("tranco")

    if "json" not in ctype.lower():
        # 레이트리밋(429)은 HTML 바디로 온다. 파싱을 시도하지 않고 바로 넘긴다.
        return None, "요청 제한(rate limit)"
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None, "응답 파싱 실패"
    ranks = data.get("ranks") or []
    if not ranks:
        return None, "Tranco 미등재"
    return ranks[0].get("rank"), None


def top_communities(items, budget, cache_path, want=3):
    """AI 커뮤니티 Top5 행과 보드 notes 를 만든다.

    사용자 질문이 "AI 트래픽이 가장 많이 모이는 커뮤니티"였으므로
    **전체 트래픽 순위(Tranco)가 주 기준**이다. 화제 유입량은 자기 참조를 뺀 뒤로
    대개 0 이라 정렬 기준이 되지 못한다 — 0 이 정직한 값이고, 그래서 주 기준이
    될 수 없다는 것도 같이 받아들인다.

    유입량이 있는 커뮤니티는 위로 올린다. 오늘 실제로 AI 화제가 그리로 흘러갔다는
    뜻이므로, 규모만 큰 곳보다 먼저 볼 값어치가 있다.

    후보 전체의 순위를 조회하되 캐시가 대부분을 흡수한다 (순위는 하루에 1 정도만
    움직인다). 첫 실행만 후보 수만큼 부르고 그 뒤로는 거의 0 이다.
    """
    notes = []
    gravity = _gravity(items)

    mentioned_domains = {d for d, g in gravity.items() if g["mentions"] > 0}
    if not mentioned_domains:
        notes.append("오늘 수집한 항목 중 다른 곳에서 커뮤니티를 가리킨 링크가 없음 "
                     "(화제 유입량 0). 전체 트래픽 순위로만 줄을 세움")

    cache = _load_cache(cache_path)
    made_call = False
    rows = []
    for c in COMMUNITIES:
        domain = c["domain"]
        g = gravity.get(domain, {"mentions": 0, "engagement": 0})

        entry = cache.get(domain)
        if entry and _cache_fresh(entry):
            rank, rank_note = entry.get("rank"), entry.get("note")
        else:
            if made_call:
                time.sleep(TRANCO_PACING_SEC)
            rank, rank_note = _fetch_rank(domain, budget, notes)
            made_call = True
            cache[domain] = dict(rank=rank, note=rank_note,
                                  checked_at=date.today().isoformat())

        rows.append(dict(
            domain=domain,
            name=c["name"],
            region=c.get("region", "global"),
            mentions=g["mentions"],
            engagement=g["engagement"],
            rank=rank,
            rank_note=rank_note,
        ))

    _save_cache(cache_path, cache)

    # 순위가 낮을수록(숫자가 작을수록) 큰 사이트다. 순위를 모르는 곳은 맨 뒤로.
    # 지역별로 따로 뽑는다. 한 표에 섞으면 국내는 규모에 밀려 한 곳도 못 올라온다.
    def order(r):
        return (0 if r["mentions"] else 1,
                -r["mentions"],
                r["rank"] if r["rank"] is not None else 10 ** 9)

    picked = []
    for region in ("global", "kr"):
        part = sorted([r for r in rows if r["region"] == region], key=order)
        picked.extend(part[:want])
    rows = picked

    if rows and all(r["rank"] is None for r in rows):
        notes.append("Tranco 전체 트래픽 순위를 하나도 못 가져옴 — "
                     "화제 유입량만으로 순위를 매김")

    notes.append("화제 유입량은 오늘 수집한 항목이 가리키는 링크 기준이고, "
                 "전체 트래픽 순위(Tranco)는 AI 화제 전용 지표가 아니라 사이트 전체 규모다.")

    # 예산 소진처럼 같은 이유가 후보마다 반복되면 노트가 같은 줄로 도배된다.
    # 순서는 유지한 채 중복만 없앤다.
    notes = list(dict.fromkeys(notes))

    return rows, notes
