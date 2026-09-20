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

import json
import os
import re
from collections import Counter
from datetime import date

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
    # 분야 이름이지 주제가 아닌 말. 사용자가 직접 지목한 것들이다.
    # 이력 기반 억제(_everyday)가 사흘 뒤부터 이 역할을 자동으로 이어받는다.
    "에이전트", "agent", "agents", "agentic", "오픈", "open", "companies",
    "company", "hack", "코딩", "coding", "개발자", "developer", "developers",
    "스킬", "skill", "skills", "도구", "tool", "tools", "플랫폼", "platform",
    "데이터", "data", "학습", "training", "추론", "성능", "기능", "업데이트",
    "update", "new", "출시", "버전", "version", "연구", "research",
    # 매체·형식어
    "techcrunch", "verge", "ars", "technica", "techmeme", "geeknews",
    "뉴스", "기사", "인터뷰", "리뷰", "칼럼", "기획", "단독", "속보",
}


# 회사 이름. 모델 업데이트 섹션이 이미 다루므로 키워드에서는 뺀다.
VENDOR_NAMES = {
    "openai", "오픈ai", "anthropic", "앤트로픽", "google", "구글", "meta", "메타",
    "microsoft", "마이크로소프트", "nvidia", "엔비디아", "xai", "mistral",
    "deepseek", "딥시크", "qwen", "alibaba", "알리바바", "naver", "네이버",
    "kakao", "카카오", "samsung", "삼성", "apple", "애플", "amazon", "아마존",
}

# 한 단어만으로 키워드가 되려면 버전 숫자가 붙은 고유명사여야 한다.
VERSIONED = re.compile(r"[A-Za-z가-힣][A-Za-z가-힣]*[-\s]?v?\d")

HISTORY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "state", "keyword-history.json")


def _load_history():
    try:
        with open(HISTORY_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {"days": [], "terms": {}}


def _save_history(hist, today, terms):
    days = [d for d in hist.get("days", []) if d != today] + [today]
    days = days[-21:]
    counts = hist.get("terms", {})
    for t in terms:
        rec = counts.setdefault(t, [])
        if today not in rec:
            rec.append(today)
        counts[t] = [d for d in rec if d in days]
    # 기록에서 사라진 말은 버린다. 파일이 무한정 커지지 않게.
    counts = {t: v for t, v in counts.items() if v}
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    tmp = HISTORY_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"days": days, "terms": counts}, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, HISTORY_PATH)


def _everyday(hist, term):
    """기록된 날의 절반 이상에 나온 말인가. 매일 나오면 정보가 아니다."""
    days = hist.get("days", [])
    if len(days) < 3:            # 이력이 얕으면 판단하지 않는다
        return False
    seen = len(hist.get("terms", {}).get(term, []))
    return seen >= max(2, len(days) // 2)


# 조각을 만드는 말. 이걸로 시작하거나 끝나는 두 단어 묶음은 주제가 아니다.
FRAGMENT_EDGE = {
    "used", "using", "use", "make", "makes", "made", "get", "gets", "take",
    "takes", "says", "said", "show", "shows", "build", "builds", "add", "adds",
    "researchers", "people", "users", "company", "companies", "team", "teams",
    "cc", "vs", "via", "per", "into", "onto", "about",
    "관련", "위해", "대해", "통한", "따른", "기반", "중인", "하는", "되는",
}


def _phrases(title):
    """붙어 있는 내용어 두 개를 묶는다. '에이전트'는 분야지만 '에이전트 운영'은 주제다."""
    words = _terms(title)
    out = []
    for a, b in zip(words, words[1:]):
        if a.lower() in FRAGMENT_EDGE or b.lower() in FRAGMENT_EDGE:
            continue
        if len(a) < 2 or len(b) < 2:
            continue
        out.append(f"{a} {b}")
    return out


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


def rows_key_space(key):
    """대표 표기를 찾기 전 단계라 키 자체로 단어 수를 판단한다."""
    return key


def extract(items, want=5, min_mentions=2):
    """(키워드 행, notes). LLM 없이 도는 임시 추출기."""
    counts = Counter()
    surface = {}
    carriers = {}

    hist = _load_history()
    today = date.today().isoformat()

    for item in items:
        # 한 제목 안에서 같은 말이 여러 번 나와도 한 번으로 센다.
        # 안 그러면 제목이 긴 기사 하나가 순위를 만든다.
        cands = _phrases(item["title"])
        # 한 단어는 (a) 버전 숫자가 붙은 고유명사이거나
        # (b) 서로 다른 출처 여러 곳이 같이 쓴 말일 때만 후보가 된다.
        # (b) 는 아래에서 출처 수로 한 번 더 거른다.
        cands += [w for w in _terms(item["title"])
                  if VERSIONED.search(w) or len(w) >= 3]
        for term in set(cands):
            if term.lower() in VENDOR_NAMES:
                continue
            if any(p.lower() in VENDOR_NAMES for p in term.split()):
                continue
            if _everyday(hist, term.lower()):
                continue
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
        # 한 단어짜리는 기준을 더 높인다 — 세 곳 이상이 같이 써야 주제로 본다.
        need = 2 if " " in rows_key_space(key) else 3
        if len(sources) < need:
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

    _save_history(hist, today, [r["keyword"].lower() for r in rows])

    notes = []
    if rows:
        notes.append("오늘의 키워드는 제목 빈도로 뽑은 임시값입니다. "
                     "ANTHROPIC_API_KEY 를 넣으면 표기가 다른 같은 주제를 "
                     "하나로 묶고 한국어 이름을 붙입니다.")
    return rows, notes
