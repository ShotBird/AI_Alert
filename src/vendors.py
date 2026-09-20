"""모델 업데이트 — 벤더별 현황판.

뉴스 피드가 아니다. "지금 각 회사의 최신 모델이 무엇이고 마지막 갱신이 언제였나"를
한 줄씩 보여주는 **상태판**이다. 같은 소식이 흘러가는 뉴스 섹션과 역할이 다르다.

**'계획'은 넣지 않는다.** 벤더는 출시 일정을 공표하지 않는다. 떠도는 소문을 일정처럼
적으면 그건 정보가 아니라 오보다. 대신 "마지막 갱신 이후 며칠"을 보여준다 —
오래 조용한 회사가 곧 뭔가 낼 가능성이 높다는 것은 사용자가 직접 읽어낼 몫이다.

**"자기 페이지를 먼저 본다"는 규칙은 그대로 적용하면 오히려 나빠진다.** 실측 결과:

  - Qwen 공식 블로그 RSS 의 최신 글은 2025-09 인데 HF 는 2026-09-20 이다. 1년 차이다.
    가중치를 공개하는 회사에게는 **HF 가 블로그보다 빠른 진짜 발표 채널**이다.
  - 반대로 xAI 는 HF 에 2025년 grok-2 만 있고 실제 최신은 x.ai/news 의 Grok 4.6 이다.

그래서 벤더를 두 갈래로 나눈다.

  클로즈드(xAI·Anthropic·OpenAI) → 자기 페이지/피드가 유일한 진실. HF 는 참고만
  오픈웨이트(Qwen·DeepSeek·Meta…)  → HF 가 본진. 블로그는 뒤처진다
"""

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

from . import vendor_pages

HF_API = "https://huggingface.co/api/models"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")

# 현황판에 고정으로 올리는 회사들. 소식이 없어도 줄은 남는다 —
# "이 회사는 조용하다"도 정보이기 때문이다.
VENDORS = [
    dict(id="anthropic", families=["Opus", "Sonnet", "Haiku", "Fable", "Mythos"], name="Anthropic", hf=None, closed=True, page=None,
         terms=["claude", "앤트로픽", "anthropic", "sonnet", "opus", "haiku"]),
    # OpenAI 는 클로즈드가 본체이고 HF 에는 오픈웨이트(gpt-oss, whisper)만 올린다.
    # 발표문 쪽이 더 최신이면 그쪽이 이긴다 — 여기는 바닥값일 뿐이다.
    dict(id="openai", families=["GPT", "o3", "o4"], name="OpenAI", hf="openai", closed=True, page=None,
         terms=["gpt", "오픈ai", "openai", "chatgpt", "o3", "o4"]),
    dict(id="google", families=["Gemini", "Gemma"], name="Google", hf="google",
         terms=["gemini", "제미나이", "gemma"]),
    dict(id="meta", families=["Llama"], name="Meta", hf="meta-llama",
         terms=["llama", "라마"]),
    # 저자명이 `xai-org` 다. `xai`/`x-ai` 로는 0건이 나와서 한동안 "소식 없음"이었다.
    # 다만 여기 올라오는 건 뒤늦게 공개하는 오픈웨이트(grok-1, grok-2)라
    # 실제 최신 모델(Grok 4.x, 클로즈드)보다 한참 뒤처진다. 발표문이 있으면 그게 이긴다.
    dict(id="xai", families=["Grok"], name="xAI", hf="xai-org", closed=True, page="xai",
         terms=["grok", "그록"]),
    dict(id="deepseek", families=["DeepSeek-V", "DeepSeek-R"], name="DeepSeek", hf="deepseek-ai",
         terms=["deepseek", "딥시크"]),
    dict(id="qwen", families=["Qwen"], name="Alibaba Qwen", hf="Qwen",
         terms=["qwen", "큐원"]),
    dict(id="moonshot", families=["Kimi"], name="Moonshot", hf="moonshotai",
         terms=["kimi", "moonshot", "문샷", "키미"]),
    dict(id="mistral", families=["Mistral", "Magistral", "Devstral"], name="Mistral", hf="mistralai",
         terms=["mistral", "미스트랄", "magistral", "devstral"]),
    dict(id="zai", families=["GLM"], name="Z.ai (GLM)", hf="zai-org",
         terms=["glm", "zhipu", "z.ai"]),
    dict(id="upstage", families=["Solar"], name="Upstage", hf="upstage",
         terms=["solar", "업스테이지", "upstage"]),
]


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _hf_latest(author):
    """이 회사가 Hugging Face 에 마지막으로 올린 모델."""
    url = (f"{HF_API}?author={author}&sort=createdAt&direction=-1&limit=5")
    try:
        data = _get(url)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError):
        return None
    for m in data or []:
        rid = m.get("id") or ""
        created = m.get("createdAt")
        if not rid or not created:
            continue
        try:
            when = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except ValueError:
            continue
        return dict(name=rid.split("/", 1)[-1], url=f"https://huggingface.co/{rid}",
                    at=when, via="Hugging Face")
    return None


def _mentions_many(title):
    """제목에 회사가 둘 이상 나오는가.

    "오픈AI, 기업 시장 점유율 역전…앤트로픽, IPO전 신형 모델 출시 검토" 같은 기사가
    Anthropic 과 OpenAI 양쪽의 '최신 모델'로 동시에 올라간 일이 있었다.
    이런 건 업계 기사이지 어느 한 회사의 출시가 아니다.
    """
    low = title.lower()
    hit = 0
    for v in VENDORS:
        if any(t in low for t in v["terms"]):
            hit += 1
            if hit > 1:
                return True
    return False


def _from_items(vendor, items):
    """수집한 항목 중 이 회사의 출시로 보이는 가장 최근 것."""
    best = None
    for item in items:
        if not item.get("is_release"):
            continue
        low = item["title"].lower()
        if not any(t in low for t in vendor["terms"]):
            continue
        # 업계 기사는 현황판에 올리지 않는다
        if _mentions_many(item["title"]):
            continue
        # "검토", "전망", "예상"은 출시가 아니다. 현황판은 일어난 일만 싣는다.
        if any(w in low for w in ("검토", "전망", "예상", "소문", "루머",
                                  "rumor", "reportedly", "could ", "may ")):
            continue
        when = item.get("published_at")
        if when is None:
            continue
        if best is None or when > best["at"]:
            best = dict(name=item["title"], url=item["url"], at=when,
                        via=item["source_name"])
    return best


# 미래를 가리키는 말. 이게 있으면 '일어난 일'이 아니라 '예정'이다.
FORWARD_WORDS = (
    "예정", "검토", "전망", "예상", "계획", "출시될", "공개될", "준비", "임박",
    "다음 달", "내달", "연내", "상반기", "하반기", "소문", "루머", "유출",
    "coming", "expected", "will launch", "will release", "set to", "plans to",
    "reportedly", "rumor", "teased", "preview of", "soon",
)

# "이건 모델 얘기다" 신호. 하나는 있어야 예정으로 인정한다.
MODEL_HINTS = ("모델", "model", "llm", "버전", "version", "preview",
               "가중치", "weights", "출시", "release", "launch", "공개")

# 모델이 아니라 요금·좌석·기능 공지. 예정 칸에 올라오면 안 된다.
NOT_MODEL = ("seat", "pricing", "plan", "business", "enterprise tier",
             "요금", "구독", "좌석", "채용", "파트너십", "투자", "ipo")

# 날짜로 읽을 만한 것. 없으면 날짜 없이 라벨만 단다.
_DATE_PATTERNS = (
    re.compile(r"(\d{4})[.\-/년]\s?(\d{1,2})[.\-/월]\s?(\d{1,2})"),
    re.compile(r"(\d{1,2})월\s?(\d{1,2})일"),
    re.compile(r"(?:on|by)\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2})",
               re.I),
)


def _pick_date(title):
    """제목에서 날짜를 건져낸다. 못 건지면 None — 지어내지 않는다."""
    for pat in _DATE_PATTERNS:
        m = pat.search(title)
        if not m:
            continue
        g = m.groups()
        if len(g) == 3:
            return f"{g[0]}-{int(g[1]):02d}-{int(g[2]):02d}"
        if len(g) == 2 and g[0].isdigit():
            return f"{int(g[0]):02d}/{int(g[1]):02d}"
        if len(g) == 2:
            return f"{g[0]} {g[1]}"
    return None


def _next_expected(vendor, items):
    """다음 예정. 벤더 자기 채널이면 '확정', 언론 관측이면 '예정'."""
    best = None
    for item in items:
        title = item.get("title") or ""
        low = title.lower()
        if not any(t in low for t in vendor["terms"]):
            continue
        if not any(w in low for w in FORWARD_WORDS):
            continue
        # 모델 얘기여야 한다. 제품명만 보면 "ChatGPT Business 좌석" 같은
        # 요금·기능 공지가 '다음 모델 예정'으로 올라온다.
        if not any(w in low for w in MODEL_HINTS):
            continue
        if any(w in low for w in NOT_MODEL):
            continue
        # 여러 회사가 든 업계 기사는 어느 한 곳의 예정이 아니다
        if _mentions_many(title):
            continue
        own_channel = (item.get("source_name") or "") == vendor["name"]
        cand = dict(
            label=title,
            url=item.get("url"),
            date=_pick_date(title),
            confidence="확정" if own_channel else "예정",
            at=item.get("published_at"),
        )
        # 확정이 예정을 이기고, 같은 등급이면 최신이 이긴다
        if best is None:
            best = cand
        elif cand["confidence"] == "확정" and best["confidence"] != "확정":
            best = cand
        elif cand["confidence"] == best["confidence"] and cand["at"] and best["at"]                 and cand["at"] > best["at"]:
            best = cand
    return best


RELEASE_WORDS = ("introduc", "announc", "launch", "releas", "unveil",
                 "now available", "available now", "출시", "공개", "발표")


def _looks_release(title):
    low = (title or "").lower()
    return any(w in low for w in RELEASE_WORDS)


def _from_page(vendor):
    """벤더 자기 뉴스 페이지에서 가장 최근 '출시'로 보이는 글."""
    if not vendor.get("page"):
        return None
    posts = vendor_pages.latest_posts(vendor["page"])
    for post in posts:                      # 이미 최신순
        if _looks_release(post["title"]):
            return dict(name=post["title"], url=post["url"], at=post["at"],
                        via=vendor["name"], channel="page")
    if posts:                               # 출시가 없으면 가장 최근 글이라도
        p = posts[0]
        return dict(name=p["title"], url=p["url"], at=p["at"],
                    via=vendor["name"], channel="page")
    return None


def _is_family_release(title, family):
    """이 제목이 그 계열의 **버전 출시**인가.

    계열 이름만 찾으면 "Grok Bot now works with X" 같은 기능 소식이 걸린다.
    계열명 바로 뒤에 버전 같은 토큰이 와야 인정한다 — Grok 4.6, Qwen3, GLM-5.3.
    """
    if not title:
        return False
    # 계열명 뒤에 한 토막(Image, Flash, K …)까지는 허용하고 그다음에 버전 숫자를 본다.
    # Qwen-Image-2.1 · Kimi-K3 는 통과하고, "Grok Bot now works with X" 는 걸린다.
    pat = re.compile(
        re.escape(family) + r"[\s\-_/]?(?:[A-Za-z]{1,10}[\s\-_/]?)?v?\d", re.I)
    return bool(pat.search(title))


def _model_name(title, family):
    """제목에서 **모델 이름만** 뽑는다.

    한 발표가 모델 둘을 싣는 일이 흔하다 —
    "Introducing Claude Fable 5.1 and Claude Mythos 5.1" 하나에서 계열 두 줄이 나오는데,
    양쪽 다 제목 전체를 싣고 있어서 같은 줄이 두 번 나온 것처럼 보였다.
    계열 이름 주변만 잘라내면 각 줄이 자기 모델을 가리킨다.
    """
    if not title:
        return title
    # 계열명 앞에 제품명 한 토막(Claude, Gemini …)까지 끌어오고, 뒤로 버전을 붙인다.
    pat = re.compile(
        r"([A-Za-z가-힣][\w.\-]*\s+)?" + re.escape(family) + r"[\s\-_]?v?[\d.]+[A-Za-z\d.\-]*",
        re.I)
    m = pat.search(title)
    if m:
        name = m.group(0).strip(" .,:")
        # "Introducing Gemini 3.8" 처럼 동사가 앞 토막으로 딸려온다. 떼어낸다.
        for verb in ("introducing", "announcing", "launching", "meet",
                     "presenting", "shipping"):
            if name.lower().startswith(verb + " "):
                name = name[len(verb) + 1:]
        return name.strip()
    # 계열이 안 보이면 원문이 낫다 — 지어내지 않는다.
    return title


def _family_rows(vendor, candidates, now):
    """계열별로 가장 최근 것. 회사 한 줄을 계열 여러 줄로 편다.

    지금까지는 회사당 한 줄이라 "그 회사가 마지막에 낸 아무거나"가 대표가 됐다.
    그래서 Meta 가 가드레일 모델로 대표되는 일이 벌어졌다.
    계열이 안 잡히면 빈 목록을 돌려주고, 호출한 쪽이 회사 줄로 되돌린다.
    """
    fams = vendor.get("families") or []
    out = []
    for fam in fams:
        best = None
        for cand in candidates:
            if not _is_family_release(cand.get("name") or "", fam):
                continue
            if best is None or cand["at"] > best["at"]:
                best = cand
        if best is None:
            continue
        days = max(0, int((now - best["at"]).total_seconds() // 86400))
        out.append(dict(vendor=vendor["name"], family=fam,
                        model=_model_name(best["name"], fam),
                        headline=best["name"],
                        url=best["url"], days=days,
                        at=best["at"].date().isoformat(),
                        via=best["via"], channel=best.get("channel"),
                        weights=bool(vendor["hf"])))
    out.sort(key=lambda r: r["days"])
    return out


def _all_candidates(vendor, items):
    """이 회사의 후보 전부 — 자기 페이지 · 피드 · HF 를 한 통에."""
    cands = []
    if vendor.get("page"):
        for post in vendor_pages.latest_posts(vendor["page"]):
            cands.append(dict(name=post["title"], url=post["url"], at=post["at"],
                              via=vendor["name"], channel="page"))
    for item in items:
        if not item.get("is_release"):
            continue
        low = (item.get("title") or "").lower()
        if not any(t in low for t in vendor["terms"]):
            continue
        if _mentions_many(item["title"]) or item.get("published_at") is None:
            continue
        cands.append(dict(name=item["title"], url=item["url"],
                          at=item["published_at"], via=item["source_name"],
                          channel="feed"))
    if vendor["hf"]:
        for m in _hf_recent(vendor["hf"]):
            cands.append(m)
    return cands


def _hf_recent(author, limit=25):
    """HF 최신 목록. 계열을 가르려면 한 건이 아니라 여러 건이 필요하다."""
    url = f"{HF_API}?author={author}&sort=createdAt&direction=-1&limit={limit}"
    try:
        data = _get(url)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError):
        return []
    out = []
    for m in data or []:
        rid, created = m.get("id") or "", m.get("createdAt")
        if not rid or not created:
            continue
        try:
            when = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except ValueError:
            continue
        out.append(dict(name=rid.split("/", 1)[-1], url=f"https://huggingface.co/{rid}",
                        at=when, via="Hugging Face", channel="hf"))
    return out


def vendor_status(items, now=None):
    """벤더별 현황 행과 notes."""
    now = now or datetime.now(timezone.utc)
    rows, notes, page_fail = [], [], []

    for vendor in VENDORS:
        closed = vendor.get("closed")

        # ① 자기 페이지 / 자기 피드 — 벤더가 직접 말한 것
        own = _from_page(vendor)
        if vendor.get("page") and own is None:
            page_fail.append(vendor["name"])
        from_news = _from_items(vendor, items)
        if from_news:
            from_news["channel"] = "feed"
            if own is None or from_news["at"] > own["at"]:
                own = from_news

        # ② Hugging Face — 가중치를 공개하는 회사에게는 여기가 본진이다
        hf = _hf_latest(vendor["hf"]) if vendor["hf"] else None
        if hf:
            hf["channel"] = "hf"

        # 클로즈드 회사는 HF 에 뒤늦은 오픈웨이트만 올라온다.
        # 자기 입으로 말한 게 있으면 그게 이긴다 — 날짜가 더 옛날이어도.
        if closed and own is not None:
            hit = own
        elif own is not None and hf is not None:
            hit = own if own["at"] >= hf["at"] else hf
        else:
            hit = own or hf

        if hit is None:
            nxt = _next_expected(vendor, items)
            rows.append(dict(vendor=vendor["name"], family=None, model=None, url=None, days=None,
                             at=None, via=None, channel=None,
                             weights=bool(vendor["hf"]),
                             next_label=(nxt or {}).get("label"),
                             next_date=(nxt or {}).get("date"),
                             next_confidence=(nxt or {}).get("confidence"),
                             next_url=(nxt or {}).get("url")))
            continue

        nxt = _next_expected(vendor, items)
        fam_rows = _family_rows(vendor, _all_candidates(vendor, items), now)
        if fam_rows:
            for fr in fam_rows:
                fr.update(next_label=(nxt or {}).get("label"),
                          next_date=(nxt or {}).get("date"),
                          next_confidence=(nxt or {}).get("confidence"),
                          next_url=(nxt or {}).get("url"))
            rows.extend(fam_rows)
            continue

        days = max(0, int((now - hit["at"]).total_seconds() // 86400))
        rows.append(dict(vendor=vendor["name"], family=None, model=hit["name"], url=hit["url"],
                         days=days, at=hit["at"].date().isoformat(),
                         via=hit["via"], channel=hit.get("channel"),
                         weights=bool(vendor["hf"]),
                         next_label=(nxt or {}).get("label"),
                         next_date=(nxt or {}).get("date"),
                         next_confidence=(nxt or {}).get("confidence"),
                         next_url=(nxt or {}).get("url")))

    rows.sort(key=lambda r: (r["days"] is None, r["days"] if r["days"] is not None else 0))

    if page_fail:
        notes.append("벤더 페이지를 못 읽은 곳: " + ", ".join(page_fail)
                     + " — 해당 회사는 피드·HF 기준으로 표시됩니다.")
    notes.append("모델 업데이트는 '현황'이지 '계획'이 아닙니다. "
                 "벤더가 출시 일정을 공표하지 않으므로 마지막 갱신 이후 경과일만 보여줍니다.")
    return rows, notes
