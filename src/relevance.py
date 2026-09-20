"""화제도 이전에 먼저 걸러야 하는 것: 이게 AI 뉴스이긴 한가.

news.hada.io(GeekNews)와 techmeme.com 은 AI 전용이 아니라 일반 테크 피드다.
실제 운영에서 "다른 언어를 배우면 뇌 건강에 좋다"와 "라즈베리파이 CEO 인터뷰"가
AI 뉴스로 보드에 실린 사고가 있었다 — 둘 다 AI 단어가 아예 없거나(전자) 스쳐
지나가듯 언급될 뿐(후자)인데, 소스 자체가 걸러주지 않으니 그대로 통과했다.
Hacker News 는 query=AI 로 긁는데, 이건 제목이 아니라 본문·URL 에도 걸리는
느슨한 검색이라 제목만 보면 신호가 아예 없는 항목도 섞여 나온다.

그래서 여기서 하는 일은 **제목 하나만 보고** AI 관련도를 0.0~1.0 점수로 매기는 것.
TechCrunch/Verge/Ars/AI타임스, Hugging Face·벤더 공식 피드는 이미 소스 단계에서
AI로 걸러져 있다 (TechCrunch 는 `/category/artificial-intelligence/` 카테고리,
AI타임스는 매체 자체가 AI 전문지다). 그런 곳을 우리가 또 문면으로 재검열하면
소스가 이미 한 일을 의심하는 꼴이라 바닥 점수를 깔아준다. 진짜로 걸러야 하는
건 일반 피드인 geeknews·techmeme·hn·etnews_ai 뿐이다.

용어는 CONTEXT.md 를 따른다 — 여기서 보는 것은 **항목**의 제목이다.
"""

import re

# ── 신뢰 소스: 이미 AI로 걸러진 피드. 문면 점수가 낮아도 바닥을 보장한다 ─────────
# techcrunch_ai/verge_ai/ars_ai 는 AI 카테고리 전용 RSS, aitimes 는 AI 전문지.
# hf_*(Hugging Face 모델 API)와 벤더 공식 피드(openai/google_blog/mistral/
# anthropic_mirror)는 애초에 AI 회사·모델 소식만 나오는 자리다.
TRUSTED_SOURCE_IDS = {
    "techcrunch_ai", "verge_ai", "ars_ai", "aitimes",
    "openai", "google_blog", "mistral", "anthropic_mirror",
}
TRUSTED_PREFIXES = ("hf_",)

TRUSTED_FLOOR = 0.75

# ── 강한 신호: 모델·벤더 고유명사. 오탐 위험이 거의 없다 ────────────────────────
STRONG_TERMS = [
    "chatgpt", "gpt", "openai", "anthropic", "claude", "gemini", "llama",
    "grok", "deepseek", "qwen", "mistral", "copilot", "sora", "midjourney",
    "perplexity", "stable diffusion", "sonnet", "opus", "haiku", "agi", "o3", "o4",
    "클로드", "제미나이", "챗gpt", "챗지피티", "그록", "딥시크", "라마", "코파일럿",
    "오픈ai", "미드저니", "인공지능", "생성형ai", "생성형 ai",
]

# ── 중간 신호: AI 업계 용어. 단어 자체는 특정 제품을 안 가리키지만 AI 밖에서는
#    거의 안 쓴다 ──────────────────────────────────────────────────────────
MEDIUM_TERMS = [
    "llm", "생성형", "프롬프트", "추론", "파인튜닝", "임베딩", "rag", "에이전트",
    "오픈웨이트", "transformer", "inference", "benchmark",
    "거대언어모델", "대규모언어모델", "추론모델", "딥러닝", "머신러닝", "신경망",
    "챗봇", "chatbot", "생성ai", "ai모델", "ai 모델",
    "machine learning", "deep learning", "neural network",
]

# ── 약한 신호: AI 기사에도 자주 나오지만 그 자체로는 다른 주제(로봇청소기,
#    반도체 실적, 감자칩...)에서도 흔하다. 혼자서는 못 넘기고 두 개 이상
#    겹치거나 medium 신호와 함께일 때만 인정한다 ────────────────────────────
WEAK_TERMS = [
    "ai", "로봇", "robot", "자동화", "automation", "알고리즘", "algorithm",
    "반도체", "semiconductor", "칩", "chip", "스타트업", "startup",
]

DEFAULT_THRESHOLD = 0.5


def _compile_boundary(term):
    # 영문/숫자 term 의 앞뒤가 다시 영문/숫자면 단어 중간이라는 뜻이다 —
    # "said"/"chair"/"campaign"/"email"/"Thailand"/"available"/"trained"/
    # "maintain" 속의 "ai" 를 여기서 막는다. 이게 이 파일에서 가장 중요한 한 줄이다.
    # 뒤에 한글 조사가 바로 붙는 경우("AI가", "AI는")는 한글이 영문/숫자가
    # 아니므로 정상적으로 매치된다 — 한글 조사는 붙여 쓰는 게 정상이라
    # \b(파이썬 정규식의 \b는 한글도 '단어 문자'로 쳐서 여기선 못 쓴다) 대신
    # 영문/숫자만 배제하는 lookaround 를 쓴다.
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])",
                       re.IGNORECASE)


_ALL_TERMS = set(STRONG_TERMS) | set(MEDIUM_TERMS) | set(WEAK_TERMS)
# 순수 영문/숫자 term 만 경계 정규식을 쓴다. 한글이 섞인 term("오픈ai", "ai모델")은
# 한글과 바로 붙여 쓰는 게 정상이라 그냥 부분 문자열로 본다 — 오탐 위험도 낮다
# (다국어 텍스트 안에서 짧은 한글 단어가 엉뚱한 곳에 우연히 끼어 있을 확률은
# 영문 "ai"가 다른 단어 속에 끼어 있을 확률보다 훨씬 낮다).
_PATTERNS = {t: _compile_boundary(t) for t in _ALL_TERMS if t.isascii()}


def _hits(text_lower, terms):
    found = []
    for term in terms:
        pat = _PATTERNS.get(term)
        matched = pat.search(text_lower) if pat else (term in text_lower)
        if matched:
            found.append(term)
    return found


def _is_trusted(source_id):
    if not source_id:
        return False
    return source_id in TRUSTED_SOURCE_IDS or source_id.startswith(TRUSTED_PREFIXES)


def _tier_score(n_strong, n_medium, n_weak):
    if n_strong:
        # 하나만 있어도 충분히 강하다. 여럿이면 살짝 더 준다.
        return min(1.0, 0.88 + 0.06 * (n_strong - 1))
    if n_medium:
        base = min(0.9, 0.62 + 0.14 * (n_medium - 1))
        if n_weak:
            base = min(1.0, base + 0.08)
        return base
    if n_weak >= 2:
        # 약한 신호 두 개가 겹치면 우연이 아니라고 본다
        # (예: "AI" + "반도체" = AI 반도체 기사일 가능성이 높다)
        return 0.55
    if n_weak == 1:
        # 약한 신호 하나뿐이면 문턱 아래에 둔다 — "감자칩", "로봇청소기" 같은
        # 완전히 다른 주제가 단어 하나 겹쳤다고 AI 뉴스가 되면 안 된다.
        return 0.15
    return 0.0


# 신뢰 소스라도 이건 뉴스가 아니다.
# TechCrunch 의 AI 카테고리에는 자기네 컨퍼런스 홍보가 섞여 들어온다.
# "6 days left to get ahead at TechCrunch Disrupt 2026" 이 실제로 뉴스 1위로 올라왔다.
# 신뢰 점수 바닥값보다 이 배제가 먼저다 — 소스를 믿는 것과 광고를 싣는 것은 다르다.
PROMO = re.compile(
    r"(disrupt \d{4}|days? left|last chance|early bird|save \$|ticket|tickets|"
    r"register now|join us at|sponsored|webinar|리크루팅|채용 설명회|"
    r"컨퍼런스 참가|사전등록|얼리버드|할인 마감|이벤트 응모)", re.I)


def is_promo(title):
    return bool(PROMO.search(title or ""))


def score(title, source_id=None):
    """제목의 AI 관련도. 0.0(무관) ~ 1.0(확실).

    소스가 이미 AI로 걸러진 신뢰 소스면 문면 점수가 낮아도 바닥을 보장한다.
    나머지는 강한/중간/약한 신호 개수로만 판단한다 — 순위가 아니라 이진 판단에
    가깝게 쓰려면 호출자가 `is_relevant` 를 쓰면 된다.
    """
    text = (title or "").lower()
    n_strong = len(_hits(text, STRONG_TERMS))
    n_medium = len(_hits(text, MEDIUM_TERMS))
    n_weak = len(_hits(text, WEAK_TERMS))

    s = _tier_score(n_strong, n_medium, n_weak)

    if _is_trusted(source_id):
        s = max(s, TRUSTED_FLOOR)

    return round(min(max(s, 0.0), 1.0), 3)


def is_relevant(title, source_id=None, threshold=DEFAULT_THRESHOLD):
    return score(title, source_id) >= threshold


if __name__ == "__main__":
    # 실제 사고 사례 2건 + 한국어 AI/비AI + "ai"를 속에 품은 함정 영단어들 +
    # 신뢰 소스 바닥값까지, 최소 25건을 표로 돌려 확인한다.
    CASES = [
        # (제목, source_id, 기대값, 메모)
        ("다른 언어를 배우는 것이 뇌 건강을 유지하는 가장 좋은 방법 중 하나일 수 있음",
         "geeknews", False, "실제 오탐 사례 1 — AI 단어 자체가 없다"),
        ("An interview with Raspberry Pi CEO Eben Upton on the future of computing",
         "techmeme", False, "실제 오탐 사례 2 — 제목엔 AI 언급이 없다"),

        ("OpenAI announces GPT-5 with major reasoning upgrades",
         "geeknews", True, "강한 신호(openai, gpt)"),
        ("구글, 제미나이 3.0 공개... 추론 능력 대폭 향상",
         "techmeme", True, "강한 신호(제미나이)"),
        ("앤스로픽 클로드, 코딩 벤치마크서 GPT-4 앞질러",
         "geeknews", True, "강한 신호(클로드, gpt)"),
        ("삼성전자, AI 반도체용 신규 칩 개발 착수",
         "hn", True, "약한 신호 3개 겹침(ai+반도체+칩)"),
        ("메타 라마4, 오픈웨이트로 공개... 추론모델 합류",
         "techmeme", True, "강한+중간 신호"),
        ("정부, 국가 AI 전략 발표...거대언어모델 자립 목표",
         "etnews_ai", True, "중간 신호(거대언어모델) — etnews_ai도 실제 필터링 대상"),
        ("딥시크發 쇼크, 중국 AI 굴기 가속",
         "geeknews", True, "강한 신호(딥시크)"),
        ("네이버 하이퍼클로바X, 생성형 AI 서비스 확대",
         "hn", True, "강한 신호(생성형 ai)"),
        ("New transformer architecture cuts inference latency by half, researchers claim",
         "hn", True, "중간 신호 2개(transformer, inference)"),
        ("국내 스타트업, RAG 기반 사내 챗봇 파인튜닝 서비스 출시",
         "hn", True, "중간 신호 3개(rag, 챗봇, 파인튜닝)"),
        ("New chip startup targets AI training workloads with custom silicon",
         "hn", True, "약한 신호 3개 겹침(chip+startup+ai)"),

        ("오늘의 서울 날씨, 전국 대체로 맑음",
         "geeknews", False, "AI 무관 — 날씨"),
        ("삼성전자, 3분기 영업이익 시장 예상치 상회",
         "techmeme", False, "AI 무관 — 실적"),
        ("손흥민, 이번 시즌 첫 골 기록",
         "hn", False, "AI 무관 — 스포츠"),
        ("김치찌개 맛있게 끓이는 법 10가지",
         "geeknews", False, "AI 무관 — 요리"),
        ("국회, 예산안 처리 놓고 여야 대치",
         "etnews_ai", False, "AI 무관 — 정치, etnews_ai도 예외 없다"),
        ("주말엔 감자칩 먹으면서 넷플릭스 정주행",
         "geeknews", False, "약한 신호 '칩' 단독 — 과자 얘기"),
        ("로봇청소기 신제품 리뷰... 흡입력 강화",
         "geeknews", False, "약한 신호 '로봇' 단독 — 가전 리뷰"),
        ("삼성전자 반도체 부문, 3분기 흑자 전환",
         "etnews_ai", False, "약한 신호 '반도체' 단독 — 일반 반도체 업황"),

        ("The chair of the campaign said the email was sent by mistake",
         "geeknews", False, "함정: chair/campaign/said/email 속의 'ai'"),
        ("New species discovered in Thailand available for public viewing",
         "techmeme", False, "함정: Thailand/available 속의 'ai'"),
        ("Engineers trained for years to maintain the aging bridge",
         "hn", False, "함정: trained/maintain/aging 속의 'ai'"),
        ("TechCrunch email newsletter: campaign finance and Thailand elections roundup",
         "techmeme", False, "함정 단어 4개 몰아넣기 — 그래도 0이어야 정상"),
        ("Available now: GPT-5 Codex ships to all Copilot users",
         "techcrunch_ai", True, "함정 단어 'available' 있어도 강한 신호(gpt)면 통과"),

        ("Best pasta recipes for autumn",
         "techcrunch_ai", True, "신뢰 소스 바닥값 확인 — 문면 신호가 없어도 뜨지 않는다"),
        ("Best pasta recipes for autumn",
         "geeknews", False, "위와 동일 제목, 신뢰 소스가 아니면 바닥값 없음"),
        ("AI타임스 창간 기념일 행사 개최",
         "aitimes", True, "신뢰 소스 바닥값 확인(aitimes)"),
    ]

    ok = 0
    for title, source_id, expected, note in CASES:
        s = score(title, source_id)
        got = is_relevant(title, source_id)
        mark = "OK" if got == expected else "FAIL"
        ok += (got == expected)
        print(f"[{mark:4}] score={s:.2f} got={got!s:5} expect={expected!s:5} "
              f"src={source_id or '-':13} {note}")
        print(f"          {title}")

    print(f"\n{ok}/{len(CASES)} 통과")
