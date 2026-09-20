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
TOKEN_THRESHOLD = 0.60
MIN_SHARED = 3

STOPWORDS = {
    "the", "a", "an", "is", "are", "to", "of", "in", "on", "for", "with", "and",
    "at", "by", "from", "as", "its", "it", "this", "that", "new", "says", "say",
    "will", "can", "how", "why", "what", "가", "이", "의", "를", "을", "에", "는",
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
        parts.scheme.lower().replace("http", "https", 1) if parts.scheme else "https",
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
        hit = None
        for c in clusters:
            if c["section"] != item["section"]:
                continue
            if _same_event(item["_norm"], item["_tok"], c["_norm"], c["_tok"]):
                hit = c
                break

        if hit is not None:
            hit["items"].append(item)
            by_url.setdefault(item["_canon"], hit)
        else:
            c = dict(section=item["section"], _norm=item["_norm"],
                     _tok=item["_tok"], items=[item])
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
