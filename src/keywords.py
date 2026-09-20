"""오늘의 키워드 — 그날 제목 전체에서 반복되는 주제를 뽑는다.

CONTEXT.md 정의대로 **별도로 수집하지 않는다.** 다른 섹션이 이미 모아온 제목에서
파생될 뿐이라, 추가 호출이 0건이고 약관 문제도 없다.

조사 결론은 "LLM 에 맡기는 게 한·영 혼재에 강하다"였고 그건 여전히 맞다.
하지만 API 키가 없다고 섹션이 비어 있으면 앱이 절반만 동작한다. 그래서 두 단계로 둔다.

  키 없음  → 여기 있는 빈도 기반 추출 (오늘 당장 돌아간다)
  키 있음  → summarize.py 가 LLM 으로 덮어쓴다 (표기 흔들림까지 정리된다)

빈도 기반의 한계는 분명하다. `GPT-6`/`gpt6`/`지피티6`를 하나로 못 묶고,
"에이전트형 코딩" 같은 **의미 묶음**은 못 만든다. 그래서 이건 임시값이라고
보드에 적어 내보낸다 — 조용히 낮은 품질을 내보내는 게 제일 나쁘다.
"""

import re
from collections import Counter

WORD = re.compile(r"[A-Za-z][A-Za-z0-9+.#-]{1,}|[가-힣]{2,}")

# 제목에 흔하지만 주제가 아닌 말. 이게 없으면 "AI"와 "모델"이 매일 1·2위를 한다.
STOP = {
    # 영어 일반
    "the", "and", "for", "with", "from", "that", "this", "its", "you", "your",
    "to", "is", "of", "in", "on", "at", "by", "as", "be", "it", "an", "or",
    "we", "us", "our", "all", "one", "two", "may", "get", "got", "let", "via",
    "up", "so", "no", "do", "does", "did", "been", "were", "and", "amp",
    "new", "now", "how", "why", "what", "who", "can", "will", "has", "have",
    "are", "was", "but", "not", "out", "more", "most", "into", "over", "about",
    "their", "они", "says", "said", "just", "off", "than", "them", "they",
    # 도메인에서 너무 흔해 변별력이 없는 말
    "ai", "llm", "model", "models", "인공지능", "모델", "기술", "서비스",
    "기업", "공개", "출시", "발표", "지원", "도입", "활용", "확대", "개발",
    "사용", "제공", "위한", "통해", "대한", "가능", "최초", "최대", "국내",
    # 매체·형식어
    "techcrunch", "verge", "ars", "technica", "techmeme", "geeknews",
    "뉴스", "기사", "인터뷰", "리뷰", "칼럼", "기획", "단독", "속보",
}


def _terms(title):
    out = []
    for raw in WORD.findall(title):
        term = raw.strip(".-#+")
        if len(term) < 2:
            continue
        low = term.lower()
        if low in STOP:
            continue
        out.append(term)
    return out


def _canonical(variants):
    """같은 말의 여러 표기 중 대표형. 가장 자주 쓰인 표기를 쓴다."""
    return variants.most_common(1)[0][0]


def extract(items, want=5, min_mentions=2):
    """(키워드 행, notes). LLM 없이 도는 임시 추출기."""
    counts = Counter()
    surface = {}
    carriers = {}

    for item in items:
        # 한 제목 안에서 같은 말이 여러 번 나와도 한 번으로 센다.
        # 안 그러면 제목이 긴 기사 하나가 순위를 만든다.
        for term in set(_terms(item["title"])):
            key = term.lower()
            counts[key] += 1
            surface.setdefault(key, Counter())[term] += 1
            carriers.setdefault(key, []).append(item)

    rows = []
    for key, n in counts.most_common(want * 4):
        if n < min_mentions:
            continue
        sources = {i["source_name"] for i in carriers[key]}
        # 한 매체만 쓰는 말은 그 매체의 상용구일 가능성이 높다 (예: "창간기획").
        if len(sources) < 2:
            continue
        rows.append(dict(
            keyword=_canonical(surface[key]),
            keyword_ko=None,          # LLM 이 붙을 때 채워진다
            mentions=n,
            source_count=len(sources),
            # "8개 항목에서 언급됐다"고만 쓰면 그 8개가 뭔지 볼 방법이 없다.
            # 화면이 바로 펼칠 수 있게 항목 자체를 들려 보낸다.
            items=[dict(title=i["title"], url=i["url"], source=i["source_name"])
                   for i in carriers[key][:6]],
        ))
        if len(rows) >= want:
            break

    notes = []
    if rows:
        notes.append("오늘의 키워드는 제목 빈도로 뽑은 임시값입니다. "
                     "ANTHROPIC_API_KEY 를 넣으면 표기가 다른 같은 주제를 "
                     "하나로 묶고 한국어 이름을 붙입니다.")
    return rows, notes
