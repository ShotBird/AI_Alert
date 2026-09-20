"""카드 한 줄 요약 + 섹션 3줄 브리핑 + 그 옆에 밀려 있던 숙제 넷.

ANTHROPIC_API_KEY 가 없는 동안은 손댈 게 없다 — `available()` 이 False 를 돌려주고
`summarize_board()` 는 노트 하나 남기고 보드를 그대로 둔다. 키가 생기는 순간
run.py 를 바꾸지 않고도 이 모듈이 알아서 켜진다.

이 파일이 채우는 다섯 가지:
  0. 카드 한 줄 요약(summary_ko) + 섹션 3줄 브리핑(briefing_ko)  — 원래 있던 것
  1. 해외 뉴스 한국어 제목(title_ko) — top_headlines 의 region=="global" 카드
  2. GitHub 스킬 한 줄 분석(note_ko) — github_skills 카드
  3. GitHub 부문 분류(category) — github_skills 카드, _classify() 의 규칙 기반 추정을 덮는다
  4. 오늘의 키워드(keyword/keyword_ko) — keywords 섹션, 표기 다른 변형을 하나로 묶는다

1·2 는 각각 board.py 가 읽는 씨앗 캐시(state/news-notes.json, state/skill-notes.json)를
그대로 덮어쓴다 — 캐시 모양이 바뀌면 board.py 도 고쳐야 하므로 모양을 지킨다.

지켜야 할 것 넷 (기존 셋 + 예산 관찰 하나):
  - **묶어서 호출한다.** 카드마다 부르지 않는다. 관심사 하나 = 요청 하나.
    다섯 관심사 중 카드/데이터가 있는 것만 부르니 하루 요청 수는 여전히 10회 안팎이다
    (아래 "토큰 비용" 참고).
  - **지어내지 않는다.** 카드에는 제목·링크·출처 이름(그리고 GitHub 카드는 영어 설명)뿐이다.
    본문을 읽은 것처럼 구체적인 수치·스펙을 만들어내지 않는다. 모델에게도 그렇게 시키고,
    응답이 깨져 있거나 카드 하나가 빠져 있으면 그 필드는 그냥 이전 값(대개 None 이거나
    규칙 기반 추정치)으로 남긴다 — 지어낸 값보다 빈 칸/추정치가 정직하다.
  - **예산은 budget.check()/spend() 로만 나간다.** github_skills.py 와 같은 모양이다.
    다섯 관심사가 같은 "anthropic" 카운터를 공유하므로, 하나라도 budget.check() 가
    막히면 그 뒤 관심사는 아예 시도하지 않는다 (막힌 채로 계속 두드려봤자 또 막힐 뿐이다).
  - **부문 목록은 새로 만들지 않는다.** github_skills.py 의 _classify() 표에 있는 이름만
    쓴다. 그 표를 이 파일이 import 할 수는 없으므로(허용된 범위가 이 파일 하나뿐이다)
    아래 CATEGORY_LIST 에 그대로 옮겨 적었다 — 표가 바뀌면 이것도 같이 바꿔야 한다.

## 토큰 비용

기존 규모는 "하루 카드 약 40장 요약 + 섹션 브리핑" 기준 월 약 ₩2,650(Sonnet 5,
docs/roadmap/ai-alert-daily-board/issues/11 참고)이었다. 새 관심사 넷은 호출 수를
하루 최대 4건만 늘린다(뉴스 제목·스킬 노트·부문 분류·키워드 각 1회 — 카드가 몇 장이든
관심사당 요청은 하나다). 페이로드 크기는 기존 카드 요약과 비슷한 자릿수
(카드당 제목+URL+출처 또는 설명 한두 문장) 이므로, 카드 수가 비슷한 날은 총 토큰이
대략 두 배가 되어 월 ₩5,000대 초반으로 늘 것으로 본다. GitHub 카드는 섹션 캡이 없어
(board.py 의 github_skills 분기는 PER_SECTION 을 적용하지 않는다) 많은 날은 스킬
노트·부문 분류 두 관심사의 토큰이 더 커질 수 있지만, 호출 "횟수"는 여전히 하루
10회 안팎(기존 최대 5 + 새 4)이라 anthropic 예산 상한(하루 60회, budget.py)에는
여유가 크다.
"""

import json
import os
import urllib.error
import urllib.request

try:
    from .budget import BudgetExceeded, BudgetUnavailable
except ImportError:  # `python src/summarize.py` 로 직접 실행할 때 (아래 __main__ 참고)
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.budget import BudgetExceeded, BudgetUnavailable

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MODEL = "claude-sonnet-5"
TIMEOUT = 60

# 섹션당 카드는 최대 5장(board.py PER_SECTION)이라 출력이 클 일이 없다.
# 넉넉히 잡아도 실제로 쓴 토큰만 과금되므로(budget_tokens 개념이 아니다) 비용에 영향 없다 —
# 다만 상한이 너무 낮으면 max_tokens 로 잘려 JSON이 깨지므로 여유를 둔다.
MAX_TOKENS = 1024

# GitHub 스킬 노트/부문 분류는 카드 수에 섹션 캡이 없다(board.py 참고) — 후보가
# 많은 날은 카드가 수십 장일 수 있어 위 MAX_TOKENS 로는 응답이 max_tokens 에 잘려
# JSON이 깨질 수 있다. 두 관심사만 넉넉히 잡는다.
MAX_TOKENS_BULK = 4096

# 단순 추출 작업이라 사고(thinking)가 필요 없다. Sonnet 5 는 기본이 adaptive thinking이라
# 켜두면 지연·토큰이 늘어난다 — 여기선 도구도 안 쓰니 "disabled"의 알려진 부작용
# (도구 호출을 본문에 흘리는 것)도 해당하지 않는다. 그래서 명시적으로 끈다.
THINKING = {"type": "disabled"}

# 카드 요약가에게 하는 지시. 결정한 것들:
#  - 제목을 한국어로 다시 쓰지 않는다 — 제목은 원문 그대로 이미 카드에 있다. 그 아래 한 줄은
#    "무엇을 의미하는지/왜 중요한지"를 말해야지 번역이면 자리 낭비다.
#  - "~라고 합니다" 류의 얼버무림 금지 — 사실을 말하듯 담백하게 쓴다. 광고 문구도 금지.
#  - 카드에 없는 사실은 모른다 — 제목·링크·출처 이름이 전부다. 모르면 구체적으로
#    쓰지 말고 애매하게 남기거나(예: "세부 스펙은 아직 공개되지 않았다"), 아예
#    이 카드는 답에서 빼도 된다. 지어내는 것보다 빈 칸이 낫다.
#  - 브리핑은 "이 3줄만 읽고 앱을 덮어도 손해가 없어야" 한다(CONTEXT.md 정의 그대로) —
#    카드 나열이 아니라 오늘 이 섹션에서 일어난 일의 요약이어야 한다.
SYSTEM_PROMPT = """\
당신은 AI/기술 소식 다이제스트를 만드는 한국어 요약가다. 매일 아침 3분 안에 읽는
보드에 들어갈 문장을 쓴다.

각 카드에 한국어 한 줄 요약(summary_ko)을 쓴다:
- 제목을 한국어로 옮기지 않는다. 제목은 원문 그대로 이미 카드에 있다. 대신 그것이
  "무엇을 의미하는지" 또는 "왜 중요한지"를 한 문장으로 쓴다.
- 평서체로 담백하게 쓴다. 광고 문구나 감탄 어조를 쓰지 않는다.
- "~라고 합니다", "~라고 전해진다" 같은 얼버무리는 말투를 쓰지 않는다. 사실을 말하듯 쓴다.
- 카드에는 제목, 링크, 출처 이름만 주어진다. 본문을 읽은 것처럼 구체적인 수치나
  스펙을 지어내지 않는다. 확실하지 않으면 애매하게 쓰거나("세부 내용은 아직
  공개되지 않았다") 그 카드는 답에서 빼라. 지어내는 것보다 빈 칸이 낫다.

섹션마다 3줄 브리핑(briefing_ko)도 쓴다:
- 이 3줄만 읽고 앱을 덮어도 그 섹션에서 오늘 알아야 할 것을 놓치지 않아야 한다.
- 카드를 하나씩 나열하지 말고, 오늘 이 섹션에서 일어난 일을 3줄로 압축한다.
- 정확히 3줄이어야 한다. 더 많거나 적으면 안 된다.

주어진 카드 목록 밖의 사실은 모른다. 응답은 주어진 JSON 스키마 형식으로만 낸다."""

# additionalProperties: false 는 구조화 출력에서 객체마다 필수다(스킬 문서 참고).
# 배열 길이 제약(예: briefing_ko 의 길이 3)은 JSON 스키마로 강제되지 않는 항목이라
# 프롬프트로 지시하고, 응답을 받은 뒤 코드에서 다시 검증한다.
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "summary_ko": {"type": "string"},
                },
                "required": ["id", "summary_ko"],
                "additionalProperties": False,
            },
        },
        "briefing_ko": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["cards", "briefing_ko"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# 1) 해외 뉴스 한국어 제목
#
# 카드에는 원문 제목만 있다. region=="global" 카드는 그 원문 제목 아래에
# title_ko(직역이 아니라 한국 독자가 바로 알아듣는 제목)를 붙인다. note 도 같이
# 받아서 state/news-notes.json 캐시 모양({title_ko, note})을 그대로 채운다 —
# 캐시 절반만 채우면 board.py 가 다음 실행에서 note_ko 를 잃는다.
# ---------------------------------------------------------------------------
NEWS_TITLE_SYSTEM_PROMPT = """\
당신은 해외 IT/AI 뉴스 제목을 한국어 독자가 한눈에 알아보는 제목으로 옮기는 편집자다.

각 기사에 대해 두 가지를 쓴다:
- title_ko: 원문 제목의 직역이 아니다. 한국어 독자가 3초 안에 무슨 일인지 알아보는
  한국어 헤드라인을 새로 쓴다. 원문에 없는 사실을 더하지 않는다.
- note: 그 기사가 왜 중요한지 또는 무슨 맥락인지 한 문장. 카드에는 제목, 링크,
  출처 이름만 주어진다. 본문을 읽은 것처럼 구체적인 수치나 인용을 지어내지 않는다.
  확실하지 않으면 애매하게 쓰거나("세부 내용은 아직 공개되지 않았다") note를
  짧게 남겨라.

평서체로 담백하게 쓴다. 광고 문구나 감탄 어조를 쓰지 않는다. 주어진 기사 목록
밖의 사실은 모른다. 응답은 주어진 JSON 스키마 형식으로만 낸다."""

NEWS_TITLE_SCHEMA = {
    "type": "object",
    "properties": {
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title_ko": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["id", "title_ko", "note"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["cards"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# 2) GitHub 스킬 한 줄 분석
#
# desc(영어 설명)를 번역하는 게 아니라 "뭘 하고 왜 쓰는지"를 쓴다.
# state/skill-notes.json 캐시(모양: {repo: "한 줄 문자열"})를 그대로 채운다.
# ---------------------------------------------------------------------------
SKILL_NOTE_SYSTEM_PROMPT = """\
당신은 GitHub 에서 뜨고 있는 에이전트 스킬/도구 레포를 한국어로 소개하는 편집자다.

각 레포에 note_ko 한 줄을 쓴다:
- 영어 설명(desc)을 그대로 번역하지 않는다. "이 레포가 무엇을 하고, 왜 쓰는지"를
  한국어로 설명한다.
- 레포 이름과 설명, URL, 종류(kind)만 주어진다. 실제로 써본 것처럼 구체적인 사용
  경험이나 수치를 지어내지 않는다. 설명이 부실해 확실하지 않으면 애매하게 쓰거나
  이 레포는 답에서 빼라. 지어내는 것보다 빈 칸이 낫다.
- 평서체로 담백하게 쓴다. 광고 문구를 쓰지 않는다.

응답은 주어진 JSON 스키마 형식으로만 낸다."""

SKILL_NOTE_SCHEMA = {
    "type": "object",
    "properties": {
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "note_ko": {"type": "string"},
                },
                "required": ["id", "note_ko"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["cards"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# 3) GitHub 부문 분류
#
# github_skills.py 의 _classify()(66~93행)가 쓰는 표를 그대로 옮겼다. 그 표가
# 바뀌면 여기도 같이 바꿔야 한다 — 이 작업의 허용 범위가 summarize.py 하나뿐이라
# import 로 공유할 수 없다. 목록 밖 이름을 만들어내지 않도록 JSON 스키마의
# enum 으로도 강제하고, 응답을 받은 뒤 코드에서 한 번 더 집합 검사를 한다.
# ---------------------------------------------------------------------------
CATEGORY_LIST = (
    "다이어그램", "디자인·UI", "슬라이드·문서", "이미지·영상", "코드리뷰",
    "테스트·품질", "프론트엔드", "백엔드·API", "데이터베이스", "인프라·배포",
    "보안", "브라우저 자동화", "크롤링·수집", "RAG·검색", "메모리·컨텍스트",
    "글쓰기", "번역·언어", "마케팅·SEO", "데이터·분석", "금융·회계", "법률·규정",
    "연구·논문", "과학·바이오", "스킬 제작", "에이전트 운영", "계획·관리",
)
ALL_CATEGORIES = CATEGORY_LIST + ("기타",)
CATEGORY_SET = frozenset(ALL_CATEGORIES)

CATEGORY_SYSTEM_PROMPT = """\
당신은 GitHub 레포를 정해진 부문(카테고리) 목록 중 하나로 분류하는 편집자다.

아래 카테고리 목록 중 그 레포에 가장 잘 맞는 것 딱 하나만 고른다:
{categories}

- 목록에 없는 새 카테고리 이름을 만들지 않는다. 반드시 목록 안에서만 고른다.
- 레포 이름과 설명(desc), 종류(kind: 스킬 / MCP 서버 / 에이전트 프레임워크 / CLI·개발도구)
  만 주어진다. 설명만으로 확실히 판단할 수 있어야 한다. 애매하거나 설명이 부실하면
  "기타"를 고른다 — 억지로 구체적인 부문에 끼워 맞추지 않는다.
- 도구 이름이나 토픽 태그에 낚이지 말 것. 예를 들어 desc 가 "코드리뷰용 CLI 에이전트"를
  만든다는 채팅 클라이언트라면, 그 레포는 코드리뷰 도구가 아니라 채팅 클라이언트다 —
  본문이 실제로 무엇을 한다고 말하는지를 본다.

응답은 주어진 JSON 스키마 형식으로만 낸다."""


def _category_system_prompt():
    return CATEGORY_SYSTEM_PROMPT.format(categories=", ".join(ALL_CATEGORIES))


CATEGORY_SCHEMA = {
    "type": "object",
    "properties": {
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "category": {"type": "string", "enum": list(ALL_CATEGORIES)},
                },
                "required": ["id", "category"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["cards"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# 4) 오늘의 키워드
#
# keywords.py 의 빈도 추출기는 표기가 다른 같은 주제(GPT-6 / gpt6 / 지피티6)를
# 못 묶고, 조사 결론대로 의미 묶음도 못 만든다. 여기서는 board 에 이미 실린
# 카드 제목들(= "그날의 항목 제목들" 중 summarize_board 가 볼 수 있는 전부)을
# 통째로 주고, 진짜 주제 5개를 한국어 이름과 함께 다시 뽑는다.
# ---------------------------------------------------------------------------
KEYWORD_SYSTEM_PROMPT = """\
당신은 그날 AI/기술 뉴스 제목들에서 반복되는 진짜 주제(키워드)를 최대 5개 뽑는 편집자다.

빈도 기반 추출기가 남긴 문제 둘을 고쳐야 한다:
- 표기가 다른 같은 주제를 하나로 묶는다 (예: "GPT-6" / "gpt6" / "지피티6" 는 한 주제다).
- "에이전트", "오픈소스" 처럼 분야 이름 자체나, 문장에서 잘려나온 조각은 주제가
  아니다. 실제 사건·제품·트렌드를 고른다.

각 주제에 대해:
- keyword: 주제를 가리키는 짧고 표준적인 표기. 고유명사는 영문 그대로 둬도 된다.
- keyword_ko: 그 주제의 한국어 이름.
- item_urls: 그 주제를 다루는 항목들의 url. 반드시 주어진 목록에 있는 url만
  그대로 골라야 한다 — 목록에 없는 url을 만들어내지 않는다. 최소 두 개를 골라야
  그 주제를 키워드로 인정한다.

같은 주제를 다루는 항목이 둘 이상인 경우만 키워드로 인정한다. 그런 주제가 5개가
안 되면 5개보다 적게 내도 된다 — 억지로 채우지 않는다. 주어진 제목 목록 밖의
사실은 모른다. 응답은 주어진 JSON 스키마 형식으로만 낸다."""

KEYWORD_SCHEMA = {
    "type": "object",
    "properties": {
        "keywords": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "keyword_ko": {"type": "string"},
                    "item_urls": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["keyword", "keyword_ko", "item_urls"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["keywords"],
    "additionalProperties": False,
}


# 씨앗 캐시 경로. board.py 가 읽는 파일과 같은 파일이어야 다음 실행에서도
# 이 결과가 살아남는다(경로 계산도 board.py 와 동일한 방식).
_STATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state")
_NEWS_NOTES_PATH = os.path.join(_STATE_DIR, "news-notes.json")
_SKILL_NOTES_PATH = os.path.join(_STATE_DIR, "skill-notes.json")


def _api_key(env):
    """run.py 의 load_env() 가 주는 dict 를 먼저 보고, 없으면 환경변수를 본다.

    github_skills 토큰을 받는 방식(run.py 118행)과 같은 우선순위다.
    """
    env = env or {}
    return env.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")


def available(env):
    """키가 있어야 이 모듈이 뭐라도 한다."""
    return bool(_api_key(env))


def _summarizable_cards(section):
    """카드 모양이 다른 '오늘의 키워드' 섹션은 summary_ko 필드가 없어 자연히 걸러진다."""
    return [c for c in section.get("cards") or [] if "summary_ko" in c]


def _card_payload(card):
    return {
        "id": card["id"],
        "title": card.get("title") or "",
        "url": card.get("url") or "",
        "sources": [s.get("name") for s in card.get("sources") or [] if s.get("name")],
    }


def _request_body(section_title, cards):
    user_content = json.dumps(
        {"section": section_title, "cards": [_card_payload(c) for c in cards]},
        ensure_ascii=False,
    )
    return {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "thinking": THINKING,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_content}],
        "output_config": {"format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}},
    }


def _post(payload, api_key):
    """HTTP 왕복. 테스트에서 이 함수만 몽키패치하면 나머지는 그대로 검증된다."""
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_json(response):
    """응답에서 구조화 출력 JSON을 꺼낸다. 모양이 어긋나면 None — 조용히 실패한다."""
    if not isinstance(response, dict):
        return None
    if response.get("stop_reason") in ("refusal", "max_tokens"):
        return None
    for block in response.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            try:
                return json.loads(block["text"])
            except (json.JSONDecodeError, KeyError, TypeError):
                return None
    return None


def _summarize_section(section, cards, api_key):
    payload = _request_body(section.get("title") or section.get("id", ""), cards)
    response = _post(payload, api_key)
    return _extract_json(response)


def _apply(section, cards, parsed):
    """파싱된 결과를 카드/섹션에 반영한다. 모양이 안 맞는 항목은 그냥 건드리지 않는다.

    누락된 카드(응답에 id가 없는 경우)는 이미 summary_ko=None 이므로 손대지 않으면
    자동으로 "빈 칸"이 된다 — 그게 이 함수가 조용히 넘어가도 되는 이유다.
    """
    changed = False
    by_id = {c["id"]: c for c in cards}

    raw_cards = parsed.get("cards") if isinstance(parsed, dict) else None
    if isinstance(raw_cards, list):
        for entry in raw_cards:
            if not isinstance(entry, dict):
                continue
            cid = entry.get("id")
            summary = entry.get("summary_ko")
            if not isinstance(cid, str) or not isinstance(summary, str):
                continue
            summary = " ".join(summary.split())  # 줄바꿈 등을 눌러 진짜 "한 줄"로 만든다
            if not summary or cid not in by_id:
                continue
            by_id[cid]["summary_ko"] = summary
            changed = True

    briefing = parsed.get("briefing_ko") if isinstance(parsed, dict) else None
    if isinstance(briefing, list):
        lines = [" ".join(b.split()) for b in briefing if isinstance(b, str) and b.strip()]
        if len(lines) == 3:
            section["briefing_ko"] = lines
            changed = True

    return changed


# ---------------------------------------------------------------------------
# 새 관심사 넷이 공유하는 작은 헬퍼들
# ---------------------------------------------------------------------------

def _call(system_prompt, schema, payload_obj, api_key, max_tokens=MAX_TOKENS):
    """concern 0 밖의 나머지 넷이 공유하는 왕복 한 벌. `_post` 하나만 패치하면
    이 함수를 쓰는 관심사도 전부 같이 검증된다(모듈 맨 아래 __main__ 참고)."""
    body = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "thinking": THINKING,
        "system": system_prompt,
        "messages": [{"role": "user", "content": json.dumps(payload_obj, ensure_ascii=False)}],
        "output_config": {"format": {"type": "json_schema", "schema": schema}},
    }
    response = _post(body, api_key)
    return _extract_json(response)


def _try_call(label, system_prompt, schema, payload_obj, api_key, budget, notes,
              max_tokens=MAX_TOKENS):
    """호출 + 파싱을 한 번에 하고, 실패하면 노트를 남기고 None 을 돌려준다.

    budget.check() 는 호출부(아래 _guard)가 이미 통과시켰다고 가정한다 — 여기서는
    "시도했으니 쓴 예산"만 처리한다(성공/실패 무관, github_skills.py 와 같은 모양).
    """
    try:
        parsed = _call(system_prompt, schema, payload_obj, api_key, max_tokens)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
            json.JSONDecodeError, OSError) as exc:
        notes.append(f"{label}: 호출 실패 ({type(exc).__name__}).")
        return None
    finally:
        budget.spend("anthropic")
    if parsed is None:
        notes.append(f"{label}: 응답을 해석하지 못해 건너뜁니다.")
    return parsed


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _write_json_atomic(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _merge_cache(path, updates):
    """씨앗 캐시에 오늘 나온 결과를 얹는다. 기존 키(예: 파일 맨 위 "_comment")는 보존한다.

    updates 의 값은 이미 "이번에 실제로 쓴 최종 값"(카드에 반영된 값, 응답이 없어
    비어 있으면 애초에 updates 에 안 들어온다)이라 그대로 덮어써도 지어낸 값이
    섞여 들어가지 않는다.
    """
    if not updates:
        return
    data = _read_json(path)
    if not isinstance(data, dict):
        data = {}
    data.update(updates)
    _write_json_atomic(path, data)


# ---------------------------------------------------------------------------
# 1) 해외 뉴스 한국어 제목
# ---------------------------------------------------------------------------

def _global_headline_cards(section):
    return [c for c in (section.get("cards") or []) if c.get("region") == "global"]


def _news_title_payload(cards):
    return {
        "concern": "news_title",
        "cards": [
            {
                "id": c["id"],
                "title": c.get("title") or "",
                "url": c.get("url") or "",
                "sources": [s.get("name") for s in c.get("sources") or [] if s.get("name")],
            }
            for c in cards
        ],
    }


def _apply_news_titles(cards, parsed):
    """title_ko/note_ko 를 카드에 얹고, 캐시에 병합할 {dedup_key: {title_ko, note}} 를 돌려준다."""
    changed = False
    cache_updates = {}
    raw = parsed.get("cards") if isinstance(parsed, dict) else None
    if not isinstance(raw, list):
        return changed, cache_updates

    by_id = {c["id"]: c for c in cards}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        cid = entry.get("id")
        title_ko = entry.get("title_ko")
        note = entry.get("note")
        if not isinstance(cid, str) or cid not in by_id:
            continue
        card = by_id[cid]
        wrote = False
        if isinstance(title_ko, str) and title_ko.strip():
            card["title_ko"] = " ".join(title_ko.split())
            wrote = True
        if isinstance(note, str) and note.strip():
            card["note_ko"] = " ".join(note.split())
            wrote = True
        if not wrote:
            continue
        changed = True
        key = card.get("dedup_key")
        if not key:
            continue
        entry_cache = {}
        if card.get("title_ko"):
            entry_cache["title_ko"] = card["title_ko"]
        if card.get("note_ko"):
            entry_cache["note"] = card["note_ko"]
        if entry_cache:
            cache_updates[key] = entry_cache
    return changed, cache_updates


# ---------------------------------------------------------------------------
# 2) GitHub 스킬 한 줄 분석
# ---------------------------------------------------------------------------

def _skill_note_payload(cards):
    return {
        "concern": "skill_note",
        "cards": [
            {
                "id": c["id"],
                "repo": c.get("repo") or "",
                "url": c.get("url") or "",
                "desc": c.get("desc") or "",
                "kind": c.get("kind") or "",
            }
            for c in cards
        ],
    }


def _apply_skill_notes(cards, parsed):
    changed = False
    cache_updates = {}
    raw = parsed.get("cards") if isinstance(parsed, dict) else None
    if not isinstance(raw, list):
        return changed, cache_updates

    by_id = {c["id"]: c for c in cards}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        cid = entry.get("id")
        note_ko = entry.get("note_ko")
        if not isinstance(cid, str) or cid not in by_id:
            continue
        if not isinstance(note_ko, str) or not note_ko.strip():
            continue
        card = by_id[cid]
        card["note_ko"] = " ".join(note_ko.split())
        changed = True
        repo = card.get("repo")
        if repo:
            cache_updates[repo] = card["note_ko"]
    return changed, cache_updates


# ---------------------------------------------------------------------------
# 3) GitHub 부문 분류
# ---------------------------------------------------------------------------

def _category_payload(cards):
    return {
        "concern": "category",
        "cards": [
            {
                "id": c["id"],
                "repo": c.get("repo") or "",
                "desc": c.get("desc") or "",
                "kind": c.get("kind") or "",
            }
            for c in cards
        ],
    }


def _apply_categories(cards, parsed):
    changed = False
    raw = parsed.get("cards") if isinstance(parsed, dict) else None
    if not isinstance(raw, list):
        return changed

    by_id = {c["id"]: c for c in cards}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        cid = entry.get("id")
        category = entry.get("category")
        if not isinstance(cid, str) or cid not in by_id:
            continue
        # 목록 밖 값이면(모델이 스키마를 어겼거나 파싱이 어그러졌거나) 규칙 기반
        # 추정치를 그대로 둔다 — 지어낸 부문보다 "기타"보다 못한 추정치가 낫다.
        if not isinstance(category, str) or category not in CATEGORY_SET:
            continue
        by_id[cid]["category"] = category
        changed = True
    return changed


# ---------------------------------------------------------------------------
# 4) 오늘의 키워드
# ---------------------------------------------------------------------------

def _keyword_item_pool(board, cap=80):
    """summarize_board 가 볼 수 있는 "그날의 항목 제목들" — board 에 이미 실린
    카드들에서 뽑는다. 원본 수집 목록(run.py 의 items)은 이 모듈에 넘어오지
    않으므로, board 카드가 우리가 가진 전부다.

    keywords 섹션 자신은 카드 제목이 아니라 각 카드의 items(원본 기사 제목들)를
    쓴다 — 그게 빈도 추출기가 이미 모아둔 진짜 항목 목록이기 때문이다.
    """
    pool, seen = [], set()
    for section in board.get("sections") or []:
        sid = section.get("id")
        for card in section.get("cards") or []:
            if sid == "keywords":
                for it in card.get("items") or []:
                    title, url = it.get("title"), it.get("url")
                    if not title or not url or url in seen:
                        continue
                    seen.add(url)
                    pool.append({"title": title, "url": url, "source": it.get("source")})
            else:
                title = card.get("title") or card.get("headline")
                url = card.get("url")
                if not title or not url or url in seen:
                    continue
                seen.add(url)
                srcs = card.get("sources") or []
                source = srcs[0].get("name") if srcs else None
                pool.append({"title": title, "url": url, "source": source})
            if len(pool) >= cap:
                return pool
    return pool


def _keyword_payload(pool):
    return {
        "concern": "keywords",
        "items": [
            {"title": p["title"], "url": p["url"], "source": p.get("source") or ""}
            for p in pool
        ],
    }


def _apply_keywords(section, pool, parsed, board_date):
    """keywords 섹션 카드를 통째로 새로 짠다. 응답이 비었거나 근거(item_urls)가
    둘 미만인 항목은 버린다 — 근거 없는 키워드는 지어낸 것과 같다.

    실패하면(파싱 실패, 모두 근거 부족 등) section["cards"] 를 건드리지 않는다.
    그러면 빈도 기반 추출기가 만든 임시 카드가 그대로 남는다 — 그게 "이전 값"이다.
    """
    raw = parsed.get("keywords") if isinstance(parsed, dict) else None
    if not isinstance(raw, list):
        return False

    url_index = {p["url"]: p for p in pool}
    prev_by_key = {c.get("dedup_key"): c for c in (section.get("cards") or [])}

    new_cards, seq = [], 0
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        kw = entry.get("keyword")
        kw_ko = entry.get("keyword_ko")
        urls = entry.get("item_urls")
        if not isinstance(kw, str) or not kw.strip():
            continue
        if not isinstance(kw_ko, str) or not kw_ko.strip():
            continue
        if not isinstance(urls, list):
            continue

        matched, matched_urls = [], set()
        for u in urls:
            if not isinstance(u, str) or u in matched_urls:
                continue
            hit = url_index.get(u)  # 목록에 없는 url은 조용히 버린다 — 지어낸 근거이기 때문
            if not hit:
                continue
            matched_urls.add(u)
            matched.append(hit)
        if len(matched) < 2:
            continue

        seq += 1
        keyword = " ".join(kw.split())
        key = keyword.lower()
        prev = prev_by_key.get(key)
        new_cards.append({
            "id": f"k_{board_date}_{seq:03d}",
            "keyword": keyword,
            "keyword_ko": " ".join(kw_ko.split()),
            "mentions": len(matched),
            "source_count": len({m.get("source") for m in matched if m.get("source")}),
            "items": [
                {"title": m["title"], "url": m["url"], "source": m.get("source")}
                for m in matched[:6]
            ],
            # 어제 대비 변화는 여기선 새로 계산할 수 없다(어제 보드가 이 모듈에
            # 안 넘어온다) — 빈도 추출기가 같은 표기로 이미 판정해둔 게 있으면
            # 그걸 물려받고, 없으면 "신규"로 둔다. "지속"을 함부로 붙이는 것보다
            # 안전한 쪽이다.
            "change": prev.get("change") if prev else "new",
            "dedup_key": key,
        })

    if not new_cards:
        return False
    section["cards"] = new_cards
    section["empty_reason"] = None
    return True


def summarize_board(board, env, budget):
    """board 를 제자리에서 채운다. 노트 목록을 돌려준다(메일/로그에 그대로 쓸 수 있게).

    키가 없으면 budget 은 건드리지도 않는다 — 호출 자체가 없으니 예산을 셀 이유가 없다.
    """
    api_key = _api_key(env)
    if not api_key:
        return ["ANTHROPIC_API_KEY가 없어 요약을 건너뜁니다. 키가 생기면 자동으로 채워집니다."]

    notes = []
    ran_any = False
    budget_ok = True

    sections = board.get("sections") or []
    sections_by_id = {s.get("id"): s for s in sections}
    board_date = board.get("board_date") or "na"

    def _guard():
        """budget.check() 를 부르고 통과하면 True. 한 번이라도 막히면 그 뒤로는
        더 시도하지 않는다(막힌 예산은 다음 관심사에서도 똑같이 막힌다)."""
        nonlocal budget_ok
        if not budget_ok:
            return False
        try:
            budget.check("anthropic")
        except (BudgetExceeded, BudgetUnavailable) as exc:
            notes.append(f"anthropic 예산 확인 실패, 이후 요약을 건너뜁니다: {exc}")
            budget_ok = False
            return False
        return True

    # ---- 0) 카드 요약 + 섹션 브리핑 ----
    for section in sections:
        cards = _summarizable_cards(section)
        if not cards:
            continue
        if not _guard():
            break

        try:
            parsed = _summarize_section(section, cards, api_key)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                json.JSONDecodeError, OSError) as exc:
            notes.append(f"{section.get('title')}: 요약 호출 실패 ({type(exc).__name__}).")
            continue
        finally:
            # 호출을 시도한 이상 성공/실패와 무관하게 예산을 쓴다 (github_skills.py 와 동일한 모양).
            budget.spend("anthropic")

        if parsed is None:
            notes.append(f"{section.get('title')}: 응답을 해석하지 못해 요약을 비워둡니다.")
            continue

        if _apply(section, cards, parsed):
            ran_any = True

    # ---- 1) 해외 뉴스 한국어 제목 ----
    top_headlines = sections_by_id.get("top_headlines")
    if top_headlines:
        global_cards = _global_headline_cards(top_headlines)
        if global_cards and _guard():
            parsed = _try_call(
                "해외 뉴스 한국어 제목", NEWS_TITLE_SYSTEM_PROMPT, NEWS_TITLE_SCHEMA,
                _news_title_payload(global_cards), api_key, budget, notes)
            if parsed is not None:
                changed, cache_updates = _apply_news_titles(global_cards, parsed)
                if changed:
                    ran_any = True
                    try:
                        _merge_cache(_NEWS_NOTES_PATH, cache_updates)
                    except OSError as exc:
                        notes.append(f"해외 뉴스 캐시 저장 실패: {type(exc).__name__}")

    # ---- 2) GitHub 스킬 한 줄 분석 / 3) GitHub 부문 분류 ----
    github_section = sections_by_id.get("github_skills")
    if github_section:
        gh_cards = github_section.get("cards") or []

        note_cards = [c for c in gh_cards if "note_ko" in c]
        if note_cards and _guard():
            parsed = _try_call(
                "GitHub 스킬 한 줄 분석", SKILL_NOTE_SYSTEM_PROMPT, SKILL_NOTE_SCHEMA,
                _skill_note_payload(note_cards), api_key, budget, notes,
                max_tokens=MAX_TOKENS_BULK)
            if parsed is not None:
                changed, cache_updates = _apply_skill_notes(note_cards, parsed)
                if changed:
                    ran_any = True
                    try:
                        _merge_cache(_SKILL_NOTES_PATH, cache_updates)
                    except OSError as exc:
                        notes.append(f"GitHub 스킬 캐시 저장 실패: {type(exc).__name__}")

        cat_cards = [c for c in gh_cards if "category" in c]
        if cat_cards and _guard():
            parsed = _try_call(
                "GitHub 부문 분류", _category_system_prompt(), CATEGORY_SCHEMA,
                _category_payload(cat_cards), api_key, budget, notes,
                max_tokens=MAX_TOKENS_BULK)
            if parsed is not None and _apply_categories(cat_cards, parsed):
                ran_any = True

    # ---- 4) 오늘의 키워드 ----
    keywords_section = sections_by_id.get("keywords")
    if keywords_section:
        pool = _keyword_item_pool(board)
        if pool and _guard():
            parsed = _try_call(
                "오늘의 키워드", KEYWORD_SYSTEM_PROMPT, KEYWORD_SCHEMA,
                _keyword_payload(pool), api_key, budget, notes)
            if parsed is not None and _apply_keywords(keywords_section, pool, parsed, board_date):
                ran_any = True

    if ran_any:
        board.setdefault("generator", {})["model"] = MODEL

    return notes


if __name__ == "__main__":
    import tempfile

    try:
        from .budget import Budget
    except ImportError:
        from src.budget import Budget

    HERE = os.path.dirname(os.path.abspath(__file__))
    ROOT = os.path.dirname(HERE)
    BOARD_PATH = os.path.join(ROOT, "boards", "latest.json")
    SCRATCH = os.environ.get("CLAUDE_SCRATCHPAD") or tempfile.gettempdir()

    print("=== 1) 키 없음 → no-op 확인 (실제 latest.json 사용) ===")
    with open(BOARD_PATH, encoding="utf-8") as fh:
        real_board = json.load(fh)
    before = json.dumps(real_board, sort_keys=True, ensure_ascii=False)

    noop_budget = Budget(os.path.join(SCRATCH, "summarize-noop-budget.json"))
    assert available({}) is False, "키가 없는데 available() 이 True"
    notes = summarize_board(real_board, {}, noop_budget)
    after = json.dumps(real_board, sort_keys=True, ensure_ascii=False)

    assert before == after, "키가 없는데 board 가 바뀌었다"
    assert isinstance(notes, list) and len(notes) == 1 and notes[0], "노트가 이상하다"
    assert "ANTHROPIC_API_KEY" in notes[0]
    print(f"  no-op 확인. 노트: {notes[0]}")

    print("\n=== 2) 가짜 전송으로 기존 카드 요약(관심사 0) 확인 ===")

    def _fake_post_v1(payload, api_key):
        body = json.loads(payload["messages"][0]["content"])
        section_title = body["section"]
        if section_title == "모델 업데이트":
            # 카드 둘 중 하나만 답에 실어서 "누락된 카드는 None으로 남는다"를 같이 검증한다.
            data = {
                "cards": [
                    {"id": "c_test_001", "summary_ko": "온디바이스 추론 속도를\n크게 끌어올렸다는 주장이다."},
                ],
                "briefing_ko": [
                    "오늘 모델 업데이트는 추론 속도 개선에 몰렸다.",
                    "두 회사가 비슷한 시기에 발표해 경쟁 구도가 드러났다.",
                    "정식 벤치마크는 아직 공개되지 않았다.",
                ],
            }
            return {
                "id": "msg_test_1", "type": "message", "role": "assistant", "model": MODEL,
                "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 120, "output_tokens": 80},
            }
        if section_title == "뉴스 Top5":
            # 스키마를 어긴 깨진 응답 — 파싱 실패해도 예외 없이 넘어가야 한다.
            return {
                "id": "msg_test_2", "type": "message", "role": "assistant", "model": MODEL,
                "content": [{"type": "text", "text": "이건 JSON이 아니다 {"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 90, "output_tokens": 10},
            }
        raise AssertionError(f"예상 못 한 섹션: {section_title}")

    orig_post = globals()["_post"]
    globals()["_post"] = _fake_post_v1
    try:
        fake_board_v1 = {
            "generator": {"model": None},
            "sections": [
                {
                    "id": "model_updates", "title": "모델 업데이트", "briefing_ko": [],
                    "empty_reason": None,
                    "cards": [
                        {"id": "c_test_001", "title": "Acme ships Model X",
                         "summary_ko": None, "url": "https://example.com/x",
                         "sources": [{"name": "Hacker News"}]},
                        {"id": "c_test_002", "title": "Beta releases Model Y",
                         "summary_ko": None, "url": "https://example.com/y",
                         "sources": [{"name": "TechCrunch"}]},
                    ],
                },
                {
                    "id": "top_headlines", "title": "뉴스 Top5", "briefing_ko": [],
                    "empty_reason": None,
                    "cards": [
                        {"id": "c_test_003", "title": "Some headline",
                         "summary_ko": None, "url": "https://example.com/z",
                         "sources": [{"name": "Techmeme"}], "region": "kr",
                         "dedup_key": "https://example.com/z"},
                    ],
                },
            ],
        }
        # 이 테스트는 관심사 0(카드 요약)만 본다 — region 을 "kr"로 둬서 관심사 1
        # (해외 뉴스 제목, region=="global"만 대상)이 끼어들지 않게 하고, "keywords"
        # 섹션 자체를 빼서 관심사 4(다른 섹션 카드 제목까지 모아 pool 을 만든다)도
        # 끼어들지 않게 한다. 관심사 1~4는 바로 아래 3)에서 따로, 확실하게 검증한다.

        fake_budget_v1 = Budget(os.path.join(SCRATCH, "summarize-fake-budget-1.json"))
        fake_notes_v1 = summarize_board(fake_board_v1, {"ANTHROPIC_API_KEY": "sk-fake-test-key"},
                                         fake_budget_v1)

        sec_model = fake_board_v1["sections"][0]
        sec_news = fake_board_v1["sections"][1]

        assert sec_model["cards"][0]["summary_ko"] == "온디바이스 추론 속도를 크게 끌어올렸다는 주장이다.", \
            sec_model["cards"][0]["summary_ko"]
        assert sec_model["cards"][1]["summary_ko"] is None, "응답에 없던 카드가 채워짐"
        assert len(sec_model["briefing_ko"]) == 3, sec_model["briefing_ko"]

        assert sec_news["cards"][0]["summary_ko"] is None, "깨진 응답인데 요약이 채워짐"
        assert sec_news["briefing_ko"] == [], "깨진 응답인데 브리핑이 채워짐"

        assert fake_board_v1["generator"]["model"] == MODEL, "성공한 섹션이 있는데 model 이 안 찍힘"
        assert any("해석하지 못해" in n for n in fake_notes_v1), fake_notes_v1

        print(f"  카드 요약 반영: {sec_model['cards'][0]['summary_ko']!r}")
        print(f"  누락 카드는 None 유지: {sec_model['cards'][1]['summary_ko']!r}")
        print(f"  브리핑 3줄: {sec_model['briefing_ko']}")
        print(f"  깨진 응답 섹션은 그대로: summary_ko={sec_news['cards'][0]['summary_ko']!r}, "
              f"briefing_ko={sec_news['briefing_ko']!r}")
        print(f"  generator.model = {fake_board_v1['generator']['model']!r}")
        print(f"  notes = {fake_notes_v1}")
    finally:
        globals()["_post"] = orig_post

    print("\n=== 3) 가짜 전송으로 새 관심사 넷(해외 뉴스 제목 / 스킬 노트 / 부문 분류 / 키워드) 확인 ===")

    def _fake_post_v2(payload, api_key):
        body = json.loads(payload["messages"][0]["content"])
        concern = body.get("concern")

        if concern == "news_title":
            data = {"cards": [
                {"id": "c_test_003", "title_ko": "테스트용 헤드라인, 한국어로",
                 "note": "테스트를 위해 지어낸 맥락 한 줄."},
            ]}
        elif concern == "skill_note":
            # 스킬 노트 쪽만 일부러 깨뜨린다 — "한 부분이 실패해도 나머지는 멀쩡해야 한다"를
            # 바로 아래(부문 분류) 관심사와 대비해서 검증하기 위해서다.
            return {
                "id": "msg_test_bad", "type": "message", "role": "assistant", "model": MODEL,
                "content": [{"type": "text", "text": "이것도 JSON이 아니다 {"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 50, "output_tokens": 5},
            }
        elif concern == "category":
            data = {"cards": [
                {"id": "c_test_101", "category": "다이어그램"},
                {"id": "c_test_102", "category": "기타"},
            ]}
        elif concern == "keywords":
            data = {"keywords": [
                {"keyword": "GPT-6", "keyword_ko": "GPT-6",
                 "item_urls": ["https://example.com/a", "https://example.com/b"]},
            ]}
        else:
            raise AssertionError(f"예상 못 한 concern: {concern}")

        return {
            "id": "msg_test_3", "type": "message", "role": "assistant", "model": MODEL,
            "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 150, "output_tokens": 60},
        }

    news_cache_path = os.path.join(SCRATCH, "summarize-test-news-notes.json")
    skill_cache_path = os.path.join(SCRATCH, "summarize-test-skill-notes.json")
    # 기존 캐시에 이미 있던 항목이 병합 뒤에도 살아남는지 보려고 미리 씨앗을 심어둔다.
    _write_json_atomic(news_cache_path, {"_comment": "seed", "https://example.com/untouched":
                                          {"title_ko": "안 건드릴 항목", "note": "그대로 있어야 한다"}})
    if os.path.exists(skill_cache_path):
        os.remove(skill_cache_path)

    orig_post = globals()["_post"]
    orig_news_path = globals()["_NEWS_NOTES_PATH"]
    orig_skill_path = globals()["_SKILL_NOTES_PATH"]
    globals()["_post"] = _fake_post_v2
    globals()["_NEWS_NOTES_PATH"] = news_cache_path
    globals()["_SKILL_NOTES_PATH"] = skill_cache_path
    try:
        fake_board_v2 = {
            "board_date": "2026-09-21",
            "generator": {"model": None},
            "sections": [
                {
                    "id": "top_headlines", "title": "뉴스 Top5", "briefing_ko": [],
                    "empty_reason": None,
                    "cards": [
                        {"id": "c_test_003", "title": "Some headline", "url": "https://example.com/z",
                         "sources": [{"name": "Techmeme"}], "region": "global",
                         "dedup_key": "https://example.com/z", "title_ko": None, "note_ko": None},
                        {"id": "c_test_004", "title": "국내 헤드라인", "url": "https://example.com/kr",
                         "sources": [{"name": "GeekNews"}], "region": "kr",
                         "dedup_key": "https://example.com/kr"},
                    ],
                },
                {
                    "id": "github_skills", "title": "GitHub 급상승", "briefing_ko": [],
                    "empty_reason": None,
                    "cards": [
                        {"id": "c_test_101", "repo": "acme/diagram-maker",
                         "url": "https://github.com/acme/diagram-maker",
                         "desc": "Turns architecture notes into rendered diagrams",
                         "kind": "스킬", "category": "코드리뷰",  # 규칙 기반이 잘못 찍은 값
                         "note_ko": None},
                        {"id": "c_test_102", "repo": "acme/resume-builder",
                         "url": "https://github.com/acme/resume-builder",
                         "desc": "Local-first resume builder, no server involved",
                         "kind": "스킬", "category": "프론트엔드",  # 규칙 기반이 잘못 찍은 값
                         "note_ko": None},
                    ],
                },
                {
                    "id": "keywords", "title": "오늘의 키워드", "briefing_ko": [],
                    "empty_reason": None,
                    "cards": [
                        {"id": "k_test_001", "keyword": "gpt6", "keyword_ko": None,
                         "mentions": 2, "source_count": 2,
                         "items": [
                             {"title": "GPT-6 leaks surface online", "url": "https://example.com/a",
                              "source": "TechCrunch"},
                             {"title": "지피티6 루머 정리", "url": "https://example.com/b",
                              "source": "GeekNews"},
                         ],
                         "change": "continuing", "dedup_key": "gpt-6"},
                    ],
                },
            ],
        }

        fake_budget_v2 = Budget(os.path.join(SCRATCH, "summarize-fake-budget-2.json"))
        fake_notes_v2 = summarize_board(fake_board_v2, {"ANTHROPIC_API_KEY": "sk-fake-test-key"},
                                         fake_budget_v2)

        sec_news = fake_board_v2["sections"][0]
        sec_gh = fake_board_v2["sections"][1]
        sec_kw = fake_board_v2["sections"][2]

        # 1) 해외 뉴스 한국어 제목 — global 카드만 채워지고 kr 카드는 그대로
        assert sec_news["cards"][0]["title_ko"] == "테스트용 헤드라인, 한국어로", sec_news["cards"][0]
        assert sec_news["cards"][0]["note_ko"] == "테스트를 위해 지어낸 맥락 한 줄.", sec_news["cards"][0]
        assert "title_ko" not in sec_news["cards"][1] or sec_news["cards"][1].get("title_ko") is None
        print(f"  해외 뉴스 title_ko: {sec_news['cards'][0]['title_ko']!r}")

        # 2) GitHub 스킬 한 줄 분석 — 이 관심사는 일부러 깨진 응답이라 note_ko 는 그대로(None)여야 한다
        assert sec_gh["cards"][0]["note_ko"] is None, "깨진 응답인데 note_ko 가 채워짐"
        assert sec_gh["cards"][1]["note_ko"] is None, "깨진 응답인데 note_ko 가 채워짐"
        assert any("스킬 한 줄 분석" in n and "해석하지 못해" in n for n in fake_notes_v2), fake_notes_v2
        print("  GitHub 스킬 노트: 깨진 응답 → note_ko 그대로(None) 확인")

        # 3) GitHub 부문 분류 — 같은 섹션인데 이 관심사는 성공해야 한다 (부분 실패 격리 확인)
        assert sec_gh["cards"][0]["category"] == "다이어그램", sec_gh["cards"][0]["category"]
        assert sec_gh["cards"][1]["category"] == "기타", sec_gh["cards"][1]["category"]
        print(f"  GitHub 부문 분류: {sec_gh['cards'][0]['category']!r}, {sec_gh['cards'][1]['category']!r}"
              " (스킬 노트가 깨졌어도 분류는 정상 반영됨)")

        # 4) 오늘의 키워드 — 카드가 통째로 교체되고, 표기가 같은 이전 카드에서 change 를 물려받는다
        assert len(sec_kw["cards"]) == 1, sec_kw["cards"]
        kw_card = sec_kw["cards"][0]
        assert kw_card["keyword"] == "GPT-6", kw_card
        assert kw_card["keyword_ko"] == "GPT-6", kw_card
        assert kw_card["mentions"] == 2, kw_card
        assert kw_card["change"] == "continuing", "이전 dedup_key(gpt-6)에서 change 를 물려받지 못함"
        assert {it["url"] for it in kw_card["items"]} == {"https://example.com/a", "https://example.com/b"}
        print(f"  오늘의 키워드: {kw_card['keyword']} / {kw_card['keyword_ko']} "
              f"(change={kw_card['change']!r}, mentions={kw_card['mentions']})")

        assert fake_board_v2["generator"]["model"] == MODEL, "성공한 관심사가 있는데 model 이 안 찍힘"

        # 5) 캐시 파일 — 뉴스 캐시는 새 항목이 기존 항목(_comment, untouched)을 보존한 채 병합됐고,
        #    스킬 캐시는 (해당 관심사가 실패했으니) 아예 쓰이지 않아야 한다.
        news_cache = _read_json(news_cache_path)
        assert news_cache.get("_comment") == "seed", "기존 캐시 주석이 사라짐"
        assert news_cache.get("https://example.com/untouched", {}).get("note") == "그대로 있어야 한다"
        assert news_cache.get("https://example.com/z") == {
            "title_ko": "테스트용 헤드라인, 한국어로",
            "note": "테스트를 위해 지어낸 맥락 한 줄.",
        }, news_cache.get("https://example.com/z")
        print(f"  news-notes 캐시 병합 확인: {news_cache.get('https://example.com/z')}")

        assert not os.path.exists(skill_cache_path), "실패한 관심사인데 skill-notes 캐시가 생성됨"
        print("  skill-notes 캐시: 관심사가 실패했으므로 파일이 생성되지 않음(정상)")

        print(f"  notes = {fake_notes_v2}")
    finally:
        globals()["_post"] = orig_post
        globals()["_NEWS_NOTES_PATH"] = orig_news_path
        globals()["_SKILL_NOTES_PATH"] = orig_skill_path

    print("\n모든 검증 통과.")
