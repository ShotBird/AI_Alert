"""묶음: 같은 사건을 말하는 항목들을 하나로 모은다.

CONTEXT.md 정의대로, 세 매체가 같은 출시를 다뤘다면 항목은 셋이고 묶음은 하나다.
이 구분이 없으면 같은 소식이 보드에서 다섯 칸을 먹는다.

조사 권고대로 싼 것부터 layer 를 쌓고, 확실해지는 즉시 멈춘다.
항목이 몇백 개 수준이라 O(n²) 비교로 충분하다 — 여기서 MinHash 같은 도구는 과하다.
"""

import re
from difflib import SequenceMatcher
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
            "ref", "fbclid", "gclid", "mc_cid", "mc_eid", "source", "__twitter_impression"}

SITE_SUFFIX = re.compile(
    r"\s*[|\-–—]\s*(TechCrunch|The Verge|Ars Technica|Techmeme|VentureBeat|"
    r"전자신문|AI타임스|GeekNews)\s*$", re.I)
NOISE = re.compile(r"[^\w\s가-힣]+")
WS = re.compile(r"\s+")

# 제목 유사도 임계값. 이보다 높으면 같은 사건으로 본다.
# 느슨하면 다른 소식이 합쳐지고, 빡빡하면 같은 소식이 여러 칸을 먹는다.
TITLE_THRESHOLD = 0.78
# 매체마다 같은 사건에 다른 제목을 단다. 문자 단위 유사도만으로는 안 잡히므로
# 내용어가 얼마나 겹치는지도 함께 본다.
#
# 2026-09-21 실측(오늘자 뉴스 묶음 100건, 서로 다른 출처 쌍만): 0.60은 실제로
# 있었던 교차 출처 중복을 전부 놓쳤다. 예를 들어
#   [The Verge] "Security researchers used Claude to help them hack into OpenAI"
#   [Ars Technica] "Researchers used Claude to hack OpenAI"
# 는 같은 사건인데 jaccard=0.56로 0.60에 근소하게 못 미쳤고,
#   [TechCrunch] "Google's Gemini is the latest AI model to hack other companies"
#   [Techmeme]   "Google says it didn't consider Gemini's hacks worthy of disclosure..."
# 는 jaccard=0.13까지 떨어진다 — Techmeme 특유의 길고 인용조 제목 때문에 분모(합집합)가
# 커져서다. 반대로 MIN_SHARED(내용어가 몇 개 겹치는가)는 오늘 데이터에서
# STOPWORDS 보강("ai"·"was"·"were"·"been" 추가, 아래 참고) 이후 3개 이상 겹치는
# 쌍이 전부 같은 사건이었다 — 즉 판별력은 비율(jaccard)이 아니라 겹치는 개수에서
# 나온다. 그래서 jaccard 문턱은 실측된 최소 참 양성(0.13)보다 살짝 낮춰 안전
# 여유만 두고, MIN_SHARED를 주 판별 기준으로 삼는다.
TOKEN_THRESHOLD = 0.12
MIN_SHARED = 3

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "been", "to", "of", "in", "on",
    "for", "with", "and", "at", "by", "from", "as", "its", "it", "this", "that",
    "new", "says", "say",
    "will", "can", "how", "why", "what",
    # "ai"는 이 섹션 제목 거의 전부에 등장해 변별력이 없다 — 있으나 없으나
    # 겹친다. 포함시켜두면 서로 다른 사건도 "ai"만으로 겹친 것처럼 보여 오탐이
    # 난다 (실측 사례: 전자신문 "CAIO 서밋..." vs AI타임스 "재귀적 자기개선..."이
    # {도입, ai, 비용}으로 3개 겹쳐 보였으나 "ai"를 빼면 2개로 떨어져 정상적으로
    # 다른 사건으로 판정된다).
    "ai",
    # "went"·"rogue"는 AI 사고 기사 제목에 흔한 상투어("AI가 폭주했다" 류)라
    # 특정 사건을 가리키지 않는다. 실측 오탐(2026-09-21): 구글 제미나이가 3개
    # 회사를 해킹한 사건과 전혀 다른 사건인 "OpenAI 모델이 폭주해 허깅페이스를
    # 해킹했다"가 {went, hacked, rogue} 3개가 겹친다는 이유로 한 묶음이 될
    # 뻔했다 — 겹친 단어 중 사건을 특정하는 고유명사(제미나이/구글/허깅페이스
    # 등)가 하나도 없었다. "went"·"rogue"를 빼면 진짜 특정 사건 쌍만 남는다.
    "went", "rogue",
    "가", "이", "의", "를", "을", "에", "는",
    "은", "도", "로", "와", "과", "한", "하는", "했다", "밝혔다",
}


def canonical_url(url):
    """추적 파라미터를 떼고 형태를 맞춘다. 가장 싸고 가장 많이 잡는 단계."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip().lower()
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=False)
             if k.lower() not in TRACKING]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((
        # http 든 https 든 같은 글로 보려고 스킴을 하나로 맞춘다.
        # 예전에는 replace("http","https") 를 썼는데 https 가 httpss 가 됐다.
        "https",
        parts.netloc.lower().removeprefix("www."),
        path,
        urlencode(sorted(query)),
        "",
    ))


def normalize_title(title):
    t = SITE_SUFFIX.sub("", title)
    t = NOISE.sub(" ", t.lower())
    return WS.sub(" ", t).strip()


def _tokens(norm_title):
    return {w for w in norm_title.split() if len(w) > 1 and w not in STOPWORDS}


def _same_event(a_norm, a_tok, b_norm, b_tok):
    """같은 사건인가. 두 갈래 중 하나만 통과하면 된다."""
    if not a_norm or not b_norm:
        return False
    # 1) 문자 단위 유사도 — 같은 기사가 여러 피드로 들어온 경우
    if min(len(a_norm), len(b_norm)) / max(len(a_norm), len(b_norm)) >= 0.55:
        if SequenceMatcher(None, a_norm, b_norm).ratio() >= TITLE_THRESHOLD:
            return True
    # 2) 내용어 겹침 — 매체가 각자 다른 제목을 단 경우
    if a_tok and b_tok:
        shared = a_tok & b_tok
        if len(shared) >= MIN_SHARED:
            jaccard = len(shared) / len(a_tok | b_tok)
            if jaccard >= TOKEN_THRESHOLD:
                return True
    return False


def build_clusters(items):
    """항목 목록을 묶음 목록으로. 각 묶음은 items 를 그대로 들고 있다."""
    clusters = []
    by_url = {}

    for item in items:
        item["_canon"] = canonical_url(item["url"])
        item["_norm"] = normalize_title(item["title"])
        item["_tok"] = _tokens(item["_norm"])

        # 1단계: 정규화한 URL 이 같으면 같은 글이다
        hit = by_url.get(item["_canon"])
        if hit is not None:
            hit["items"].append(item)
            continue

        # 2단계: 제목이 충분히 비슷하면 같은 사건으로 본다
        # 묶음을 처음 만든 항목의 제목하고만 비교하면 안 된다 — 실측 사례
        # (2026-09-21, Anthropic 생물학 연구소 기사): 로이터의 한 URL 이 약한
        # 제목("Anthropic creates AI powered wetlab")으로 먼저 묶음을 만들었고,
        # 같은 URL 의 다른 제목 변형("Anthropic sets up biology lab...")이 URL
        # 일치로 그 묶음에 조용히 합류했다. 그 뒤로 TechCrunch 의 진짜 같은
        # 사건 기사가 들어와도 묶음의 "대표 제목"은 여전히 처음 그대로라 비교가
        # 실패했다. 그래서 묶음 안의 모든 항목과 비교해 하나라도 맞으면 합친다.
        hit = None
        for c in clusters:
            if c["section"] != item["section"]:
                continue
            if any(_same_event(item["_norm"], item["_tok"], m["_norm"], m["_tok"])
                   for m in c["items"]):
                hit = c
                break

        if hit is not None:
            hit["items"].append(item)
            by_url.setdefault(item["_canon"], hit)
        else:
            c = dict(section=item["section"], items=[item])
            clusters.append(c)
            by_url[item["_canon"]] = c

    for c in clusters:
        _finalize(c)
    return clusters


def _finalize(cluster):
    items = cluster["items"]
    dated = [i for i in items if i.get("published_at")]
    # 대표 항목: 반응 수치가 가장 큰 것, 없으면 가장 먼저 나온 것
    lead = max(items, key=lambda i: (i.get("engagement") or 0))
    cluster["title"] = lead["title"]
    cluster["url"] = lead["url"]
    cluster["published_at"] = min((i["published_at"] for i in dated), default=None)
    # 출처는 수집 경로 단위로 센다. 같은 출처가 두 번 세어지지 않는다.
    cluster["sources"] = sorted({i["source_name"] for i in items})
    cluster["source_count"] = len(cluster["sources"])
    cluster["is_release"] = any(i.get("is_release") for i in items)
    # 국내 소스가 하나라도 물려 있으면 국내로 본다. 같은 사건을 양쪽이 다뤘다면
    # 한국 독자에게는 국내 기사가 더 쓸모 있다.
    cluster["region"] = "kr" if any(i.get("region") == "kr" for i in items) else "global"
    cluster["engagement"] = max((i.get("engagement") or 0) for i in items)
    cluster["comments"] = max((i.get("comments") or 0) for i in items)
