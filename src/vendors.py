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
from datetime import date, datetime, timedelta, timezone

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
#
# 2026-09-21 실측(수집 항목 2,099건): 벤더 이름이 든 제목 691건 중 이 목록에
# 걸린 것이 **4건**뿐이었다. 목록이 좁은 탓도 있었다 — "teased"는 있는데
# "teases"가 없고, "plans to"는 있는데 "planning to"가 없었다. 어형만 넓힌다.
# 넓혀도 쓰레기가 들어오지 않는 이유는 아래 `_pick_when` 이 **날짜·기간을
# 못 뽑으면 후보를 통째로 버리기** 때문이다.
FORWARD_WORDS = (
    "예정", "검토", "전망", "예상", "계획", "출시될", "공개될", "준비", "임박",
    "다음 달", "내달", "연내", "상반기", "하반기", "소문", "루머", "유출",
    "예고", "앞두", "차기", "로드맵", "티저", "사전 예약",
    "coming", "expected", "will launch", "will release", "will arrive",
    "will ship", "will be available", "set to", "plans to", "planning to",
    "to launch", "to release", "to debut", "slated", "due in", "upcoming",
    "reportedly", "rumor", "rumour", "tease", "preview of", "soon",
    "roadmap", "in the works",
)

# "이건 모델 얘기다" 신호. 하나는 있어야 예정으로 인정한다.
MODEL_HINTS = ("모델", "model", "llm", "버전", "version", "preview",
               "가중치", "weights", "출시", "release", "launch", "공개")

# 모델이 아니라 요금·좌석·기능 공지. 예정 칸에 올라오면 안 된다.
NOT_MODEL = ("seat", "pricing", "plan", "business", "enterprise tier",
             "요금", "구독", "좌석", "채용", "파트너십", "투자", "ipo")

# ── '언제' 뽑기 ──────────────────────────────────────────────────────────────
# 다음 예정 칸은 **날짜 칸**이다. 예전에는 label 에 제목 전체를 넣어서, 후보가
# 하나만 걸려도 좁은 표 칸에 기사 헤드라인이 통째로 들어갔다. 칸에는 "10/15",
# "4분기", "연내" 같은 짧은 말만 넣고 헤드라인은 next_url 링크(↗)로만 닿게 한다.
#
# 그래서 규칙이 하나 더 생긴다: **날짜든 기간이든 못 뽑으면 후보가 아니다.**
# "언제인지 모르는 예정"은 예정표에 적을 내용이 없다.

_MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
_MONTH_NO = {m.lower(): i + 1 for i, m in enumerate(_MONTHS.split("|"))}

# 영어 달 이름은 앞에 시점을 가리키는 말이 있어야 인정한다. 그냥 두면 오늘
# 피드에 실제로 있는 "March 20 ChatGPT outage" 가 '다음 예정 3/20' 으로,
# "New in ChatGPT for Business: April 2025" 가 '2025.4' 로 올라온다.
_EN_LEAD = r"(?:on|by|in|from|starting|beginning|during|early|late|mid)\s+"

_P_YMD = re.compile(r"(20\d{2})[.\-/년]\s?(\d{1,2})[.\-/월]\s?(\d{1,2})")
_P_KO_MD = re.compile(r"(\d{1,2})월\s?(\d{1,2})일")
_P_EN_DAY = re.compile(_EN_LEAD + r"(" + _MONTHS + r")[a-z]*\.?\s+(\d{1,2})\b", re.I)
_P_EN_MON = re.compile(_EN_LEAD + r"(" + _MONTHS + r")[a-z]*\.?(?:\s+(20\d{2}))?\b", re.I)
_P_KO_Q = re.compile(r"([1-4])\s?분기")
_P_EN_Q = re.compile(r"\bQ([1-4])\b")
_P_KO_MON = re.compile(r"(\d{1,2})월(?!\s?\d)")

# 이미 앞날인 것이 확실한 말들. 끝나는 날을 따로 계산하지 않는다.
_OPEN_PERIODS = (
    ("내년 상반기", "내년 상반기"), ("내년 하반기", "내년 하반기"),
    ("내년 초", "내년 초"), ("내년", "내년"),
    ("연내", "연내"), ("올해 안", "연내"), ("올해 말", "연말"), ("연말", "연말"),
    ("이달 말", "이달 말"), ("내달", "내달"), ("다음 달", "내달"), ("다음달", "내달"),
    ("다음 주", "다음 주"), ("다음주", "다음 주"),
    ("early next year", "내년 초"), ("next year", "내년"),
    ("later this year", "연내"), ("end of the year", "연말"), ("year-end", "연말"),
    ("next month", "내달"), ("next week", "다음 주"),
    ("coming weeks", "몇 주 내"), ("coming days", "며칠 내"),
    ("coming months", "몇 달 내"),
)


def _month_end(year, month):
    return (date(year + (month == 12), 1 if month == 12 else month + 1, 1)
            - timedelta(days=1))


def _when(label, until, iso=None):
    return dict(label=label, date=iso, until=until)


def _read_when(title, today):
    """제목에서 '언제'를 읽는다. dict(label=표시용 짧은 말, date=ISO, until=기간 끝).

    `until` 은 "이 말이 가리키는 기간의 마지막 날"이다. 앞날인지 판정하는 데만 쓴다.
    이미 앞날인 것이 분명한 말(연내·내년·내달)에는 None 을 둔다. 못 읽으면 None.
    """
    low = title.lower()

    m = _P_YMD.search(title)                       # 2026-10-15 · 2026년 10월 15일
    if m:
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            d = None
        if d:
            return _when(f"{d.month}/{d.day}", d, d.isoformat())

    m = _P_KO_MD.search(title)                     # 10월 15일
    if m:
        try:
            d = date(today.year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            d = None
        if d:
            return _when(f"{d.month}/{d.day}", d, d.isoformat())

    m = _P_EN_DAY.search(title)                    # on October 15
    if m:
        try:
            d = date(today.year, _MONTH_NO[m.group(1)[:3].lower()], int(m.group(2)))
        except ValueError:
            d = None
        if d:
            return _when(f"{d.month}/{d.day}", d, d.isoformat())

    m = _P_KO_Q.search(title) or _P_EN_Q.search(title)      # 4분기 · Q4
    if m:
        q = int(m.group(1))
        if "내년" in title or "next year" in low:
            return _when(f"내년 {q}분기", None)
        return _when(f"{q}분기", _month_end(today.year, q * 3))

    # "내년 상반기" 는 아래 _OPEN_PERIODS 가 그대로 받는다. 올해 상·하반기만
    # 여기서 끝나는 날을 계산한다 — 9월에 "상반기"는 이미 지나간 말이다.
    if ("상반기" in title or "하반기" in title) and "내년" not in title:
        half = "상반기" if "상반기" in title else "하반기"
        return _when(half, _month_end(today.year, 6 if half == "상반기" else 12))

    for needle, label in _OPEN_PERIODS:
        if needle in title or needle in low:
            return _when(label, None)

    m = _P_EN_MON.search(title)                    # in November · in November 2026
    if m:
        year = int(m.group(2)) if m.group(2) else today.year
        month = _MONTH_NO[m.group(1)[:3].lower()]
        return _when(f"{month}월" if year == today.year else f"{year}.{month}",
                     _month_end(year, month))

    m = _P_KO_MON.search(title)                    # 10월 (일자 없이)
    if m:
        month = int(m.group(1))
        if 1 <= month <= 12:
            return _when(f"{month}월", _month_end(today.year, month))

    return None


# ── '개발 단계' 신호 ────────────────────────────────────────────────────────
# 2026-09-21 실측: Gemini 를 언급한 39건 중 FORWARD_WORDS 에 걸린 것이 **1건**
# 뿐이었는데, 정작 그 39건 안에는 이런 것들이 있었다.
#
#   Google **prepares** Gemini App for Avatars, Plugins, and **Gemini 4**
#   Google **is working on** Plugins for Gemini Enterprise
#   Google **tests** Computer Use on Gemini Desktop
#   Google **develops** AI Rooms for Gemini Enterprise
#
# 미출시 소식을 다루는 매체는 미래형을 쓰지 않는다. **현재형으로 미출시를 말한다.**
# "곧 나온다"가 아니라 "지금 만들고 있다"가 이 바닥의 문법이다.
#
# 이런 글에는 날짜가 없다. 그래서 날짜 대신 **단계**를 싣는다 —
# 없는 날짜를 지어내는 대신, 아는 만큼만 "준비 중"이라고 적는다.
_DEV_STAGES = (
    (("준비 중", "준비중", "prepares", "preparing", "readying", "gearing up"), "준비 중"),
    (("개발 중", "개발중", "is working on", "are working on", "develops",
      "developing", "in development", "building a new", "구축 중"), "개발 중"),
    (("테스트 중", "시험 중", "tests ", "testing ", "trials", "experimenting",
      "internal testing", "a/b test"), "테스트 중"),
    (("early look", "첫 공개", "사전 공개", "spotted", "appears in",
      "발견됐다", "포착"), "사전 포착"),
)


def _dev_stage(blob):
    """'아직 안 나왔고 만들고 있다'는 신호. 없으면 None."""
    low = (blob or "").lower()
    for words, label in _DEV_STAGES:
        if any(w in low for w in words):
            return label
    return None


# 계열명 바로 뒤에 버전이 오는 형태. "Gemini 4" 는 모델 얘기고
# "Gemini Notebook" 은 기능 얘기다. MODEL_HINTS 만으로는 이 둘이 안 갈린다.
_FAMILY_VER_CACHE = {}


def _mentions_model(blob, vendor):
    """이 글이 **모델** 얘기인가. 기능·앱 소식을 예정표에서 걷어내는 문지기."""
    low = (blob or "").lower()
    if any(w in low for w in MODEL_HINTS):
        return True
    for fam in (vendor.get("families") or []):
        pat = _FAMILY_VER_CACHE.get(fam)
        if pat is None:
            pat = re.compile(re.escape(fam) + r"[\s\-_]?v?\d", re.I)
            _FAMILY_VER_CACHE[fam] = pat
        if pat.search(blob or ""):
            return True
    return False


def _pick_when(title, now=None):
    """제목에서 **앞날의** 날짜·기간만 뽑는다. 지난 날짜는 예정이 아니다."""
    if not title:
        return None
    today = (now or datetime.now(timezone.utc)).date()
    got = _read_when(title, today)
    if not got:
        return None
    if got["until"] is not None and got["until"] < today:
        # 지나간 날짜다. "[9월18일] …" 같은 날짜 머리표가 예정으로 올라오는 걸 막는다.
        return None
    return got


# 오래전 기사에서 '예정'을 긁어오면 계획이 아니라 역사다. OpenAI 피드 하나가
# 2015년치까지 1,210건을 준다 — 창이 없으면 10년 전 "coming soon" 이 오늘의
# 예정이 된다. 현황판(마지막 갱신)과 달리 예정은 최근에 나온 말만 유효하다.
NEXT_WINDOW_DAYS = 60


def _next_expected(vendor, items, now=None):
    """다음 예정. 벤더 자기 채널이면 '확정', 언론 관측이면 '예정'."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=NEXT_WINDOW_DAYS)
    best = None
    for item in items:
        title = item.get("title") or ""
        low = title.lower()
        at = item.get("published_at")
        if at is None or at < cutoff:
            continue
        # **회사 판정은 제목으로만** 한다. 본문까지 보면 "구글도 비슷한 걸 준비 중"
        # 한 줄 때문에 남의 회사 기사가 그 회사의 예정으로 붙는다.
        if not any(t in low for t in vendor["terms"]):
            continue
        # 반면 **언제인지는 본문에 있다.** 루머 기사 제목은 "Meta to give Muse its
        # own mailbox" 처럼 미래형만 싣고 날짜는 리드 문단에 적는다. 제목만 보던
        # 동안 이 칸은 구조적으로 채워질 수 없었다.
        blob = (title + " " + (item.get("summary") or "")).strip()
        low_blob = blob.lower()
        # 앞날을 가리키는 말이거나, **지금 만들고 있다**는 말이거나. 둘 중 하나는
        # 있어야 한다. 미출시 전문 매체는 미래형을 거의 쓰지 않는다.
        # 개발 단계 판정은 **미출시 전문 매체에만** 쓴다. 일반 매체가 쓰는
        # "tests"·"building" 은 대개 다른 뜻이다 — 실제로 "Claude now leads a
        # quarter of work **building** its…"(클로드가 코드를 짓는다)와
        # "Third-party cyber evaluations"(평가)가 예정으로 올라왔다.
        stage = _dev_stage(blob) if item.get("rumor") else None
        if not stage and not any(w in low_blob for w in FORWARD_WORDS):
            continue
        # 모델 얘기여야 한다. 제품명만 보면 "ChatGPT Business 좌석" 같은
        # 요금·기능 공지가, "Gemini Notebook 도구" 같은 앱 소식이 예정표에 오른다.
        if not _mentions_model(blob, vendor):
            continue
        # 요금·좌석·채용 얘기는 **제목으로** 거른다. 본문까지 보면 거의 모든
        # 기사가 어딘가에서 'plan' 이나 'business' 를 말하므로 다 걸린다.
        if any(w in low for w in NOT_MODEL):
            continue
        # 여러 회사가 든 업계 기사는 어느 한 곳의 예정이 아니다
        if _mentions_many(title):
            continue
        # 날짜를 집었으면 그 날짜를, 못 집었으면 **단계**를 적는다.
        # 둘 다 없으면 예정표에 쓸 말이 없다.
        when = _pick_when(blob, now)
        if when is None and stage is None:
            continue
        own_channel = (item.get("source_name") or "") == vendor["name"]
        cand = dict(
            label=when["label"] if when else stage,   # 10/15 · 4분기 · 연내 · 준비 중
            headline=title,                  # 근거 헤드라인. 칸이 아니라 링크로 닿는다
            url=item.get("url"),
            date=when["date"] if when else None,
            # 회사 자기 채널이라도 **날짜를 말하지 않았으면 확정이 아니다.**
            # "테스트 중"을 확정이라고 적으면 없는 약속을 만들어내는 것이다.
            confidence="확정" if (own_channel and when is not None) else "예정",
            dated=when is not None,
            at=at,
        )
        if best is None or _better_next(cand, best):
            best = cand
    return best


def _better_next(a, b):
    """예정 후보 우열. 확정 > 날짜 있는 예정 > 단계만 아는 예정, 같으면 최신."""
    rank = lambda c: (c["confidence"] == "확정", bool(c.get("dated")))
    ra, rb = rank(a), rank(b)
    if ra != rb:
        return ra > rb
    return bool(a.get("at") and b.get("at") and a["at"] > b["at"])


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
    #
    # 버전 앞에 이름 한 토막이 더 붙는 모델이 있다 — `GPT-Live-1`, `Qwen-Image-2.1`.
    # 숫자만 기다리면 이런 것들은 아예 안 걸려서 제목 전체가 표에 실렸다
    # ("OpenAI launches GPT-Live-1 for full-duplex voice agents" 가 모델명 칸에 있었다).
    pat = re.compile(
        r"([A-Za-z가-힣][\w.\-]*\s+)?" + re.escape(family)
        + r"(?:[\s\-_](?:[A-Za-z]{2,12})){0,2}[\s\-_]?v?[\d.]+[A-Za-z\d.\-]*",
        re.I)
    m = pat.search(title)
    if m:
        return _strip_noise(m.group(0).strip(" .,:"))
    # 계열이 안 보이면 원문이 낫다 — 지어내지 않는다. 다만 원문 그대로 실으면
    # `Qwen/Qwen-Image-2.1` 처럼 소유자 접두사가, `Introducing …` 처럼 동사가
    # 표에 그대로 나온다. 지어내지 않으면서 군더더기만 떼는 건 별개다.
    return _strip_noise(title)


# 앞머리 동사. "Introducing Gemini 3.8" 에서 모델은 뒤쪽뿐이다.
_LEAD_VERBS = ("introducing", "announcing", "launching", "meet", "presenting",
               "shipping", "say hello to", "welcome", "bringing", "releases",
               "release", "launches", "unveils", "announces", "introduces",
               "debuts", "출시", "공개", "발표",
               # 원형도 붙는다 — "to launch Gemini 4" 에서 앞 토막으로 딸려왔다
               "launch", "unveil", "announce", "introduce", "debut", "ship",
               "present", "reveals", "reveal")

# "<회사> launches <모델>" 처럼 동사 앞에 회사 이름이 한두 토막 붙는 형태.
_VENDOR_VERB_RE = re.compile(
    r"^[\w.\-]+(?:\s+[\w.\-]+)?\s+"
    r"(?:launch\w*|releas\w*|unveil\w*|announc\w*|introduc\w*|debut\w*|ship\w*)\s+",
    re.I)

# 계열명 앞 토막으로 딸려오는 접속사·관사. 모델 이름의 일부가 아니다 —
# "Introducing Claude Fable 5.1 and Claude Mythos 5.1" 에서 두 번째 줄이
# `and Mythos 5.1` 로 나왔다.
_LEAD_STOPWORDS = ("and", "or", "with", "the", "a", "an", "plus", "&",
                   "for", "to", "in", "of", "그리고", "및", "와", "과")


def _strip_noise(name):
    """모델 이름에서 표시용 군더더기만 뗀다. 없는 말을 만들지는 않는다."""
    if not name:
        return name
    # Hugging Face 는 `소유자/모델` 로 온다. 회사 칸이 이미 소유자를 말하고 있으므로
    # 표에서 접두사는 같은 말을 두 번 하는 것이고, 좁은 폰에서 모델명을 밀어낸다.
    if "/" in name and " " not in name.split("/")[0]:
        name = name.split("/", 1)[1]

    name = _VENDOR_VERB_RE.sub("", name, count=1)

    # 앞머리 군더더기는 한 겹이 아니다 — "Meta and Llama 4" 는 동사와 접속사가
    # 겹쳐 붙는다. 더 뗄 것이 없을 때까지 돈다. 다만 전부 떼고 빈 문자열이
    # 되는 일은 막는다 — 이름이 없는 것보다 군더더기 붙은 이름이 낫다.
    for _ in range(4):
        low = name.lower()
        for word in _LEAD_VERBS + _LEAD_STOPWORDS:
            if low.startswith(word + " ") and len(name) > len(word) + 1:
                name = name[len(word) + 1:]
                break
        else:
            break
    return name.strip(" .,:-")


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
            nxt = _next_expected(vendor, items, now)
            rows.append(dict(vendor=vendor["name"], family=None, model=None, url=None, days=None,
                             at=None, via=None, channel=None,
                             weights=bool(vendor["hf"]),
                             next_label=(nxt or {}).get("label"),
                             next_date=(nxt or {}).get("date"),
                             next_confidence=(nxt or {}).get("confidence"),
                             next_url=(nxt or {}).get("url")))
            continue

        nxt = _next_expected(vendor, items, now)
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

    # '다음 예정'이 전부 비는 날이 대부분이다. 빈칸을 설명 없이 두면 수집이
    # 고장 난 것처럼 보이므로, 왜 비었는지를 숫자로 적는다.
    # 2026-09-21 실측: 벤더 이름이 든 제목 691건 중 앞날의 날짜·기간을 말한 것 0건.
    filled = sum(1 for r in rows if r.get("next_label"))
    if not filled:
        notes.append(
            f"'다음 예정'이 모두 비어 있습니다 — 최근 {NEXT_WINDOW_DAYS}일 수집분에 "
            "앞으로의 모델 일정(날짜·분기·'연내')을 적은 제목이 한 건도 없었습니다. "
            "칸을 채우려고 기준을 낮추면 틀린 날짜가 올라가므로 빈칸으로 둡니다.")
    return rows, notes
