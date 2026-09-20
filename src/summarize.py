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

**2026-09-21 수정.** 위 추정은 "섹션당 카드 5장"을 전제했는데 실제 보드는 그렇지 않다.
오늘자 boards/latest.json 기준 github_skills 45장, communities 23장, model_updates 14장,
top_headlines 8장이다. 호출 "횟수"는 추정대로 하루 9~10회가 맞지만(예산 60회에 여유),
토큰량은 카드 수에 비례하므로 월 ₩6,000~7,000 쪽이 정직한 숫자다. 아래 max_tokens
상향은 **비용을 올리지 않는다** — max_tokens 는 예약이 아니라 상한이고 실제로 생성한
토큰만 과금되기 때문이다. 오히려 지금까지는 상한에 걸려 잘린(= 파싱 실패한) 응답에
돈만 내고 결과를 못 얻었을 것이다.

## 공식 문서로 확인한 요청 계약 (2026-09-21, platform.claude.com)

이 파일은 실제 API 에 한 번도 나가본 적이 없다. 그래서 문서를 읽고 필드 단위로 맞췄다.

  - 모델: `claude-sonnet-5` 는 현재 유효한 Messages API 모델 ID 다(1M 컨텍스트,
    최대 출력 128K, $2/$10 per MTok). 날짜 접미사를 붙이지 않는다.
    https://platform.claude.com/docs/en/about-claude/models/overview
  - 구조화 출력: `output_config.format = {"type": "json_schema", "schema": ...}` 가
    현재 철자다(옛 `output_format` 은 폐기). **베타 헤더가 필요 없다.** 응답은
    `content` 안의 `text` 블록 하나에 스키마를 지킨 JSON 문자열로 오고
    `stop_reason` 은 `end_turn` 이다.
    https://platform.claude.com/docs/en/build-with-claude/structured-outputs
    스키마 제약: 모든 객체에 `required` 와 `additionalProperties: false` 필수.
    `enum`(문자열)·중첩 객체·객체 배열은 지원. `minLength`/`maxLength`/`maximum`/
    `maxItems` 는 **미지원 — 쓰면 400.** (아래 스키마들은 전부 이 범위 안이다.)
  - thinking: Sonnet 5 는 기본이 adaptive 라 켜져 있다. 문서가 "Claude Sonnet 5 에서는
    끌 수 있다"고 명시하며 `{"type": "disabled"}` 예시를 준다. 끌 수 없는 모델은
    Fable 5/5.1·Mythos 계열이고 Sonnet 5 는 해당하지 않는다. `budget_tokens` 는
    Sonnet 5 에서 제거됐고 보내면 400 이다 — 이 파일은 쓰지 않는다.
    https://platform.claude.com/docs/en/build-with-claude/thinking
  - 헤더: `x-api-key`(필수) + `anthropic-version` + `content-type` 이면 완전하다.
    `anthropic-beta` 는 필요 없다.
    https://platform.claude.com/docs/en/api/messages
  - 오류: 400/401/402/403/404/413 은 재시도해도 똑같이 실패한다. 429/5xx/529 만
    재시도 대상이고 `retry-after` 헤더를 존중한다.
    https://platform.claude.com/docs/en/api/errors
"""

import json
import os
import time
import urllib.error
import urllib.request

try:
    from .board import GITHUB_SECTION_TITLE
    from .budget import BudgetExceeded, BudgetUnavailable
except ImportError:  # `python src/summarize.py` 로 직접 실행할 때 (아래 __main__ 참고)
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.board import GITHUB_SECTION_TITLE
    from src.budget import BudgetExceeded, BudgetUnavailable

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MODEL = "claude-sonnet-5"

# 스트리밍을 쓰지 않으므로 응답 전체가 올 때까지 이 소켓이 열려 있다. 카드가 많은
# 섹션(오늘 기준 github_skills 45장)은 출력이 수천 토큰이라 60초로는 모자란다.
# 하루 한 번 도는 배치라 넉넉히 잡아도 손해가 없다.
TIMEOUT = 240

# --- max_tokens ---------------------------------------------------------
# 예전 값(1024)은 "섹션당 카드 최대 5장"을 전제로 한 숫자였는데 그 전제가 틀렸다.
# board.py 의 github_skills 분기는 PER_SECTION 을 적용하지 않고, 실제 보드에는
# 45장이 들어 있다. 카드 45장에 한국어 한 줄씩이면 출력만 3,000 토큰이 넘어
# 1024 에서는 **매번** max_tokens 로 잘리고, 잘린 JSON 은 반드시 파싱에 실패한다.
# = 돈은 내고 결과는 0. 그래서 카드 수에 맞춰 잡는다.
#
# max_tokens 는 "예약"이 아니라 "상한"이고 실제 생성한 토큰만 과금된다. 넉넉히
# 잡는 것 자체에는 비용이 없다. 상한선(CAP)은 비용이 아니라 TIMEOUT 안에 받아낼
# 수 있는 현실적 한계에서 온다.
MAX_TOKENS_FLOOR = 2048      # 카드가 없어도 섹션 브리핑 3줄 + 여유
MAX_TOKENS_PER_CARD = 120    # 한국어 한 줄(≈60자) + id + JSON 구분자에 넉넉한 여유
MAX_TOKENS_CAP = 16000       # Sonnet 5 는 128K 까지 되지만 스트리밍 없이는 이쪽이 한계

# 예전 이름은 남겨 둔다(바깥에서 import 해 보는 곳이 있을 수 있다).
# 이제는 "카드 수를 모를 때 쓰는 기본값" 이라는 뜻이다.
MAX_TOKENS = MAX_TOKENS_FLOOR
MAX_TOKENS_BULK = MAX_TOKENS_CAP


def _max_tokens_for(card_count):
    """카드 수에 맞춘 출력 상한. 아무리 많아도 CAP 을 넘지 않는다."""
    n = max(0, int(card_count or 0))
    return min(MAX_TOKENS_CAP, MAX_TOKENS_FLOOR + n * MAX_TOKENS_PER_CARD)


# --- 한 요청에 담는 카드 수 ------------------------------------------------
# "관심사 하나 = 요청 하나"는 지키되, 카드 수는 막아야 한다. 오늘자 보드의
# github_skills 섹션에는 카드가 1,160장 있다. 그대로 한 요청에 실으면 입력만
# 8만 토큰이고 출력은 7만 토큰이 필요해 max_tokens 로도, 비용으로도 감당이 안 된다
# (관심사 셋이 같은 섹션을 보므로 하루 $0.5 = 월 ₩2만이 그 섹션 하나에서 나온다).
#
# 카드는 board.py 가 이미 순위대로 정렬해 두었으므로 **앞에서부터** 이만큼만 채운다.
# 나머지는 손대지 않아 빈 칸으로 남는다 — 그리고 그 사실을 섹션 노트에 적는다.
# 지어내는 것보다, 그리고 예산을 태우는 것보다 빈 칸이 낫다.
MAX_CARDS_PER_REQUEST = 40


def _cap_cards(cards):
    return list(cards)[:MAX_CARDS_PER_REQUEST]


# --- 재시도 -------------------------------------------------------------
# 문서(api/errors)가 재시도 대상이라고 말하는 것만 재시도한다. 400/401/403/404 를
# 다시 보내봤자 똑같이 실패하고, 관심사 다섯이 각각 한 번씩 두드리면 헛돈만 다섯 번이다.
RETRYABLE_STATUS = frozenset({408, 409, 429, 500, 502, 503, 504, 529})
RETRY_ATTEMPTS = 2           # 최초 1회 + 재시도 1회
RETRY_WAIT_DEFAULT = 5       # retry-after 헤더가 없을 때
RETRY_WAIT_CAP = 30          # 헤더가 아무리 큰 값을 줘도 이만큼만 기다린다

# 단순 추출 작업이라 사고(thinking)가 필요 없다. Sonnet 5 는 기본이 adaptive thinking이라
# (문서: "On Claude Sonnet 5, where thinking is on by default, you can turn it off")
# 켜두면 지연·토큰이 늘어난다 — 여기선 도구도 안 쓰니 "disabled"의 알려진 부작용
# (도구 호출을 본문에 흘리는 것)도 해당하지 않는다. 그래서 명시적으로 끈다.
# budget_tokens 는 Sonnet 5 에서 제거된 필드라 절대 넣지 않는다(넣으면 400).
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
        "max_tokens": _max_tokens_for(len(cards)),
        "thinking": THINKING,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_content}],
        "output_config": {"format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}},
    }


def _post(payload, api_key):
    """HTTP 왕복. 테스트에서 이 함수만 몽키패치하면 나머지는 그대로 검증된다.

    헤더 셋은 문서(api/messages) 기준으로 완전하다 — x-api-key(필수),
    anthropic-version, content-type. 구조화 출력은 정식 기능이라 anthropic-beta
    헤더가 필요 없다(있으면 오히려 "Unexpected value" 400 을 맞을 수 있다).
    """
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


# ---------------------------------------------------------------------------
# 오류 분류와 재시도
#
# 예전에는 모든 예외가 "호출 실패 (HTTPError)" 한 줄로 뭉개지고, 실패해도 다음
# 관심사가 똑같이 한 번 더 두드렸다. 키가 틀렸으면(401) 그게 다섯 번 반복되고,
# 429 면 막힌 문을 다섯 번 더 두드린 뒤 보드는 아무 설명 없이 비어 있었다.
# 이제는 "다시 보내도 소용없는 실패"와 "잠깐 기다리면 되는 실패"를 갈라서,
# 전자는 즉시 전체 중단, 후자는 한 번만 기다렸다 재시도한 뒤 역시 전체 중단한다.
# ---------------------------------------------------------------------------

class _Halt(Exception):
    """이 실패 뒤로는 남은 LLM 작업을 전부 멈춰야 한다는 뜻. reason 은 한국어 설명."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


_STATUS_REASON = {
    400: "요청이 거부됐습니다(400). 모델 ID·스키마·파라미터를 확인해야 합니다",
    401: "ANTHROPIC_API_KEY 가 유효하지 않습니다(401)",
    402: "결제 정보에 문제가 있습니다(402)",
    403: "이 키에는 권한이 없습니다(403)",
    404: f"모델 ID 를 찾을 수 없습니다(404, {MODEL})",
    413: "요청이 너무 큽니다(413). 카드 수를 줄여야 합니다",
    429: "호출 한도에 걸렸습니다(429)",
    529: "서버가 과부하입니다(529)",
}


def _retry_after_seconds(exc):
    """429/503 의 retry-after 헤더를 존중하되 상한을 둔다."""
    raw = None
    headers = getattr(exc, "headers", None)
    if headers is not None:
        try:
            raw = headers.get("retry-after")
        except Exception:
            raw = None
    try:
        wait = int(float(raw))
    except (TypeError, ValueError):
        wait = RETRY_WAIT_DEFAULT
    return max(1, min(RETRY_WAIT_CAP, wait))


def _describe_failure(exc):
    """(재시도해도 되는가, 한국어 설명) — 노트에 그대로 쓸 수 있는 문장."""
    if isinstance(exc, urllib.error.HTTPError):
        code = exc.code
        reason = _STATUS_REASON.get(code)
        if reason is None:
            reason = (f"서버 오류({code})" if code >= 500
                      else f"요청이 거부됐습니다({code})")
        return code in RETRYABLE_STATUS, reason
    if isinstance(exc, (TimeoutError, urllib.error.URLError, OSError)):
        return True, f"네트워크 문제로 응답을 받지 못했습니다({type(exc).__name__})"
    if isinstance(exc, json.JSONDecodeError):
        # 200 인데 본문이 JSON 이 아니다. 다시 보내도 같을 가능성이 높다.
        return False, "응답 본문이 JSON 이 아닙니다"
    return False, f"알 수 없는 실패({type(exc).__name__})"


def _post_once(payload, api_key, budget):
    """예산을 쓰고 한 번 보낸다. budget.check() 는 호출부가 이미 통과시켰다고 본다."""
    try:
        return _post(payload, api_key)
    finally:
        # 보낸 이상 성공/실패와 무관하게 예산을 쓴다 (github_skills.py 와 같은 모양).
        budget.spend("anthropic")


def _post_guarded(payload, api_key, budget, label):
    """재시도까지 포함한 왕복. 끝내 실패하면 _Halt 를 올려 전체를 멈춘다."""
    last_reason = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return _post_once(payload, api_key, budget)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                json.JSONDecodeError, OSError) as exc:
            retryable, reason = _describe_failure(exc)
            last_reason = reason
            if not retryable or attempt == RETRY_ATTEMPTS - 1:
                break
            # 재시도분도 예산을 쓴다. 남아 있는지 먼저 확인한다(fail-closed 유지).
            try:
                budget.check("anthropic")
            except (BudgetExceeded, BudgetUnavailable) as bexc:
                raise _Halt(f"{label}: {reason}. 재시도 예산이 없습니다 ({bexc})") from exc
            time.sleep(_retry_after_seconds(exc))
    raise _Halt(f"{label}: {last_reason}. 이후 요약을 건너뜁니다.")


def _extract_json(response):
    """응답에서 구조화 출력 JSON을 꺼낸다. 꺼내지 못하면 None.

    문서가 말하는 모양(build-with-claude/structured-outputs)에 맞춘다:
      - 성공하면 `stop_reason` 은 "end_turn",
      - JSON 은 `content` 안의 **text 블록** 문자열이다.
    도구를 함께 쓰면 text 가 아닌 블록이 섞일 수 있다고 문서가 말하므로, 첫 블록만
    보지 않고 text 블록을 차례로 시도한다(우리는 도구를 안 쓰지만 공짜인 방어다).

    거절하는 stop_reason 둘:
      - "refusal"   : 안전 분류기가 거절했다. content 에 쓸 게 없다.
      - "max_tokens": 출력이 잘렸다 → JSON 이 반드시 깨져 있다.
    나머지("end_turn"/"stop_sequence"/"tool_use"/"pause_turn")는 통과시키고 파싱으로 판정한다.
    """
    return _extract_json_with_reason(response)[0]


def _extract_json_with_reason(response):
    """(parsed, 실패 이유) — 실패 이유를 노트에 그대로 쓰기 위해 나눠 둔다."""
    if not isinstance(response, dict):
        return None, "응답이 JSON 객체가 아닙니다"

    stop = response.get("stop_reason")
    if stop == "refusal":
        detail = response.get("stop_details") or {}
        category = detail.get("category") if isinstance(detail, dict) else None
        return None, ("모델이 응답을 거절했습니다"
                      + (f" (분류: {category})" if category else ""))
    if stop == "max_tokens":
        return None, "응답이 max_tokens 에 잘렸습니다(상한을 올려야 합니다)"

    texts = [b.get("text") for b in (response.get("content") or [])
             if isinstance(b, dict) and b.get("type") == "text"
             and isinstance(b.get("text"), str)]
    if not texts:
        return None, "응답에 text 블록이 없습니다"

    for text in texts:
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed, None
    return None, "text 블록을 JSON 으로 읽지 못했습니다"


def _summarize_section(section, cards, api_key, budget, label):
    payload = _request_body(section.get("title") or section.get("id", ""), cards)
    response = _post_guarded(payload, api_key, budget, label)
    return _extract_json_with_reason(response)


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

def _request_body_for(system_prompt, schema, payload_obj, max_tokens):
    """관심사 1~4 가 보내는 요청 본문. 관심사 0(_request_body)과 같은 모양이다."""
    return {
        "model": MODEL,
        "max_tokens": max_tokens,
        "thinking": THINKING,
        "system": system_prompt,
        "messages": [{"role": "user", "content": json.dumps(payload_obj, ensure_ascii=False)}],
        "output_config": {"format": {"type": "json_schema", "schema": schema}},
    }


def _call(system_prompt, schema, payload_obj, api_key, budget, label,
          max_tokens=MAX_TOKENS):
    """concern 0 밖의 나머지 넷이 공유하는 왕복 한 벌. `_post` 하나만 패치하면
    이 함수를 쓰는 관심사도 전부 같이 검증된다(모듈 맨 아래 __main__ 참고)."""
    body = _request_body_for(system_prompt, schema, payload_obj, max_tokens)
    response = _post_guarded(body, api_key, budget, label)
    return _extract_json_with_reason(response)


def _try_call(label, system_prompt, schema, payload_obj, api_key, budget, notes,
              max_tokens=MAX_TOKENS):
    """호출 + 파싱. 파싱에 실패하면 노트를 남기고 None 을 돌려준다.

    budget.check() 는 호출부(아래 _guard)가 이미 통과시켰다고 가정한다. 예산 차감은
    `_post_once` 가 보낸 횟수만큼 한다(재시도도 한 번의 호출이다).

    HTTP 실패는 여기서 삼키지 않는다 — `_post_guarded` 가 `_Halt` 를 올리고
    `summarize_board` 가 그걸 받아 **남은 관심사를 전부 멈춘다.** 401 을 다섯 번
    두드리거나 429 를 다섯 번 더 때리지 않기 위해서다.
    """
    parsed, reason = _call(system_prompt, schema, payload_obj, api_key, budget,
                           label, max_tokens)
    if parsed is None:
        notes.append(f"{label}: {reason or '응답을 해석하지 못했습니다'}. 건너뜁니다.")
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


# ---------------------------------------------------------------------------
# 5) 빈 칸을 정직하게 설명한다
#
# 오늘 사용자가 본 증상: "해외 뉴스 4건 중 1건만 한국어 제목이 있다." 원인은 버그가
# 아니라 키가 없는 것이었다 — 번역은 손으로 넣어둔 씨앗 캐시(state/news-notes.json,
# URL 4개)에서만 오고 URL 이 정확히 일치할 때만 붙는다. 문제는 **보드가 그 말을 안
# 한다는 것**이다. 그래서 고장처럼 보인다.
#
# board.py 는 이미 섹션마다 notes 통로를 갖고 있고(web/index.html 의 .s-notes 가
# 그린다) run.py 는 수집기 노트를 거기에 넣는다. 요약도 같은 통로를 쓴다.
#
# 이 스위치를 False 로 두면 이 모듈은 보드의 어떤 필드도 건드리지 않고(= 키가
# 없을 때 보드가 바이트 단위로 동일) 노트는 반환값으로만 나간다. 되돌리는 데
# 한 줄이면 되도록 남겨둔 것이다.
# ---------------------------------------------------------------------------
EMIT_SECTION_NOTES = True


def _note_section(section, text):
    """섹션 notes 에 한 줄 더한다. 같은 말을 두 번 넣지 않는다."""
    if not EMIT_SECTION_NOTES or not section or not text:
        return
    notes = section.get("notes")
    if not isinstance(notes, list):
        notes = []
        section["notes"] = notes
    if text not in notes:
        notes.append(text)


def _capped_note(total, used, what):
    return (f"{what}: 카드 {total}장 중 앞의 {used}장만 채웠습니다 "
            f"(한 요청에 담는 한도 {MAX_CARDS_PER_REQUEST}장). "
            "나머지는 지어내지 않고 빈 칸으로 둡니다.")


def _already_said(section, *keywords):
    """이 섹션에 같은 말을 하는 노트가 이미 있으면 True.

    run.py/board.py 쪽에서 붙인 안내가 이미 있을 수 있다. 같은 말을 두 번 하면
    화면만 지저분해지므로, 키 얘기를 하면서 같은 낱말을 쓰는 노트가 있으면 비킨다.
    """
    for n in section.get("notes") or []:
        if (isinstance(n, str) and "ANTHROPIC_API_KEY" in n
                and all(k in n for k in keywords)):
            return True
    return False


def _mark_missing(board, why, done=()):
    """LLM 이 채웠어야 할 칸이 비어 있는 섹션마다 이유를 한 줄 남긴다.

    `why` 는 "ANTHROPIC_API_KEY 가 없어" 처럼 뒷말에 이어 붙는 조각이다.
    `done` 은 이번 실행에서 실제로 성공한 관심사 이름들 — 성공한 관심사에 대고
    "아직 안 됐다"고 말하지 않기 위해서다.

    이미 채워져 있는 섹션에는 아무 말도 하지 않는다. 다 된 섹션에 변명을 붙이면
    그게 더 헷갈린다.
    """
    for section in board.get("sections") or []:
        sid = section.get("id")
        cards = section.get("cards") or []
        lines = []

        blank = sum(1 for c in cards if "summary_ko" in c and not c.get("summary_ko"))
        if blank:
            lines.append(f"{why} 카드 {blank}장의 한 줄 요약이 비어 있습니다.")
        if cards and not (section.get("briefing_ko") or []):
            lines.append(f"{why} 이 섹션의 3줄 브리핑이 비어 있습니다.")

        if sid == "top_headlines":
            glob = [c for c in cards if c.get("region") == "global"]
            miss = [c for c in glob if not c.get("title_ko")]
            if miss:
                lines.append(
                    f"{why} 해외 기사 {len(glob)}건 중 {len(miss)}건에 한국어 제목이 "
                    "없습니다. 지금은 손으로 넣어둔 캐시(state/news-notes.json)에 "
                    "URL 이 똑같은 기사에만 한국어 제목이 붙습니다.")
        elif sid == "github_skills":
            miss = [c for c in cards if "note_ko" in c and not c.get("note_ko")]
            if miss:
                lines.append(f"{why} 레포 {len(miss)}개의 한 줄 설명이 비어 있습니다.")
            if ("category" not in done and any("category" in c for c in cards)
                    and not _already_said(section, "부문")):
                lines.append(f"{why} 부문은 규칙 기반 추정치 그대로입니다.")
        elif (sid == "keywords" and cards and "keywords" not in done
                and not _already_said(section, "키워드")):
            lines.append(
                f"{why} 키워드는 빈도 기반 추출기의 결과 그대로입니다 "
                "(표기가 다른 같은 주제가 따로 잡혀 있을 수 있습니다).")

        for line in lines:
            _note_section(section, line)


def summarize_board(board, env, budget):
    """board 를 제자리에서 채운다. 노트 목록을 돌려준다(메일/로그에 그대로 쓸 수 있게).

    키가 없으면 budget 은 건드리지도 않는다 — 호출 자체가 없으니 예산을 셀 이유가 없다.
    키가 없어도 **비어 있는 칸이 왜 비었는지**는 섹션 notes 에 남긴다
    (EMIT_SECTION_NOTES 참고). 카드 내용은 여전히 한 글자도 건드리지 않는다.
    """
    api_key = _api_key(env)
    if not api_key:
        _mark_missing(board, "ANTHROPIC_API_KEY 가 없어")
        return ["ANTHROPIC_API_KEY가 없어 요약을 건너뜁니다. 키가 생기면 자동으로 채워집니다."]

    notes = []
    ran_any = False
    budget_ok = True
    halted = None
    done = set()

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

    try:
        # ---- 0) 카드 요약 + 섹션 브리핑 ----
        for section in sections:
            all_cards = _summarizable_cards(section)
            cards = _cap_cards(all_cards)
            if not cards:
                continue
            if not _guard():
                break
            if len(all_cards) > len(cards):
                _note_section(section, _capped_note(len(all_cards), len(cards), "한 줄 요약"))

            label = section.get("title") or section.get("id") or "섹션 요약"
            parsed, reason = _summarize_section(section, cards, api_key, budget, label)
            if parsed is None:
                notes.append(f"{label}: {reason or '응답을 해석하지 못했습니다'}. 요약을 비워둡니다.")
                continue

            if _apply(section, cards, parsed):
                ran_any = True

        # ---- 1) 해외 뉴스 한국어 제목 ----
        top_headlines = sections_by_id.get("top_headlines")
        if top_headlines:
            global_cards = _cap_cards(_global_headline_cards(top_headlines))
            if global_cards and _guard():
                parsed = _try_call(
                    "해외 뉴스 한국어 제목", NEWS_TITLE_SYSTEM_PROMPT, NEWS_TITLE_SCHEMA,
                    _news_title_payload(global_cards), api_key, budget, notes,
                    max_tokens=_max_tokens_for(len(global_cards)))
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

            all_note_cards = [c for c in gh_cards if "note_ko" in c]
            note_cards = _cap_cards(all_note_cards)
            if note_cards and len(all_note_cards) > len(note_cards):
                _note_section(github_section,
                              _capped_note(len(all_note_cards), len(note_cards), "한 줄 설명"))
            if note_cards and _guard():
                parsed = _try_call(
                    "GitHub 스킬 한 줄 분석", SKILL_NOTE_SYSTEM_PROMPT, SKILL_NOTE_SCHEMA,
                    _skill_note_payload(note_cards), api_key, budget, notes,
                    max_tokens=_max_tokens_for(len(note_cards)))
                if parsed is not None:
                    changed, cache_updates = _apply_skill_notes(note_cards, parsed)
                    if changed:
                        ran_any = True
                        try:
                            _merge_cache(_SKILL_NOTES_PATH, cache_updates)
                        except OSError as exc:
                            notes.append(f"GitHub 스킬 캐시 저장 실패: {type(exc).__name__}")

            all_cat_cards = [c for c in gh_cards if "category" in c]
            cat_cards = _cap_cards(all_cat_cards)
            if cat_cards and len(all_cat_cards) > len(cat_cards):
                _note_section(github_section,
                              _capped_note(len(all_cat_cards), len(cat_cards), "부문 분류"))
            if cat_cards and _guard():
                parsed = _try_call(
                    "GitHub 부문 분류", _category_system_prompt(), CATEGORY_SCHEMA,
                    _category_payload(cat_cards), api_key, budget, notes,
                    # 부문은 카드당 한 낱말이라 한 줄 설명보다 훨씬 짧다.
                    max_tokens=_max_tokens_for(len(cat_cards) // 3))
                if parsed is not None and _apply_categories(cat_cards, parsed):
                    ran_any = True
                    done.add("category")

        # ---- 4) 오늘의 키워드 ----
        keywords_section = sections_by_id.get("keywords")
        if keywords_section:
            pool = _keyword_item_pool(board)
            if pool and _guard():
                parsed = _try_call(
                    "오늘의 키워드", KEYWORD_SYSTEM_PROMPT, KEYWORD_SCHEMA,
                    _keyword_payload(pool), api_key, budget, notes,
                    # 출력은 주제 5개 × (이름 둘 + url 몇 개)라 카드 수가 아니라
                    # 이 고정 규모에 맞춘다. url 이 길어서 floor 만으로는 빠듯하다.
                    max_tokens=_max_tokens_for(20))
                if parsed is not None and _apply_keywords(keywords_section, pool, parsed, board_date):
                    ran_any = True
                    done.add("keywords")
    except _Halt as halt:
        # 다시 보내도 소용없는 실패(401/400/404 …)거나, 재시도까지 했는데도 안 된
        # 실패(429/5xx)다. 남은 관심사는 아예 시도하지 않는다.
        notes.append(halt.reason)
        halted = halt.reason

    if ran_any:
        board.setdefault("generator", {})["model"] = MODEL

    # 비어 있는 칸이 왜 비었는지 섹션마다 한 줄. 사용자가 "고장인가?"를 묻지 않아도 되게.
    if halted:
        _mark_missing(board, "요약 호출이 중단되어", done)
    elif not budget_ok:
        _mark_missing(board, "하루 호출 예산이 다 되어", done)
    else:
        _mark_missing(board, "모델이 이 항목을 채우지 못해", done)

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

    print("=== 1a) 키 없음 + EMIT_SECTION_NOTES=False → 보드가 바이트 단위로 동일 ===")
    with open(BOARD_PATH, encoding="utf-8") as fh:
        real_board = json.load(fh)
    before = json.dumps(real_board, sort_keys=True, ensure_ascii=False)

    noop_budget = Budget(os.path.join(SCRATCH, "summarize-noop-budget.json"))
    assert available({}) is False, "키가 없는데 available() 이 True"

    _emit_orig = EMIT_SECTION_NOTES
    globals()["EMIT_SECTION_NOTES"] = False
    try:
        notes = summarize_board(real_board, {}, noop_budget)
    finally:
        globals()["EMIT_SECTION_NOTES"] = _emit_orig
    after = json.dumps(real_board, sort_keys=True, ensure_ascii=False)

    assert before == after, "키가 없는데 board 가 바뀌었다"
    assert isinstance(notes, list) and len(notes) == 1 and notes[0], "노트가 이상하다"
    assert "ANTHROPIC_API_KEY" in notes[0]
    assert noop_budget.counts.get("anthropic") is None, "키가 없는데 예산을 썼다"
    print(f"  바이트 동일 확인. 노트: {notes[0]}")

    print("\n=== 1b) 키 없음 + EMIT_SECTION_NOTES=True → 달라지는 것이 notes 뿐인지 ===")
    with open(BOARD_PATH, encoding="utf-8") as fh:
        real_board2 = json.load(fh)
    assert EMIT_SECTION_NOTES is True, "기본값이 True 여야 한다"
    notes2 = summarize_board(real_board2, {}, noop_budget)

    # 섹션의 notes 만 빼고 비교한다 — 카드 한 글자도 달라지면 안 된다.
    def _strip_section_notes(b):
        clone = json.loads(json.dumps(b, ensure_ascii=False))
        for sec in clone.get("sections") or []:
            sec.pop("notes", None)
        return json.dumps(clone, sort_keys=True, ensure_ascii=False)

    assert _strip_section_notes(real_board2) == _strip_section_notes(json.loads(before)), \
        "notes 말고 다른 것이 바뀌었다"
    added = {s.get("id"): [n for n in (s.get("notes") or [])]
             for s in real_board2.get("sections") or []}
    assert any(v for v in added.values()), "설명 노트가 하나도 안 붙었다"
    assert notes2 == notes, "boardwide 노트는 그대로여야 한다"
    for sid, lines in added.items():
        for line in lines:
            print(f"  [{sid}] {line}")

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
        assert any("JSON 으로 읽지 못했습니다" in n for n in fake_notes_v1), fake_notes_v1

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
                    # 제목은 board.py 한 곳에서만 정한다. 예전엔 여기에 문자열을
                    # 따로 적어두어, 보드 제목을 바꿔도 이 점검은 옛 제목을 봤다.
                    "id": "github_skills", "title": GITHUB_SECTION_TITLE, "briefing_ko": [],
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
        assert any("스킬 한 줄 분석" in n and "JSON 으로 읽지 못했습니다" in n
                   for n in fake_notes_v2), fake_notes_v2
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

    # -----------------------------------------------------------------------
    # 4) 다섯 관심사가 **실제로 보내는** 요청 본문을 찍고, 문서와 필드 단위로 대조한다.
    #    키가 없어 진짜로 보내본 적이 없으므로, 보내기 직전의 dict 를 잡아서 본다.
    # -----------------------------------------------------------------------
    print("\n=== 4) 다섯 관심사의 요청 본문 — 문서와 필드 단위 대조 ===")

    # 문서가 허용하지 않는 JSON 스키마 키워드. 쓰면 400 이 온다.
    #   https://platform.claude.com/docs/en/build-with-claude/structured-outputs
    UNSUPPORTED_SCHEMA_KEYS = {
        "minLength", "maxLength", "minimum", "maximum", "exclusiveMinimum",
        "exclusiveMaximum", "multipleOf", "maxItems", "uniqueItems",
        "patternProperties", "propertyNames", "if", "then", "else", "not",
    }

    def _check_schema(node, path="schema"):
        """구조화 출력이 받아주는 JSON 스키마 부분집합인지 재귀로 확인한다."""
        assert isinstance(node, dict), f"{path}: 스키마 노드가 dict 가 아니다"
        bad = UNSUPPORTED_SCHEMA_KEYS & set(node)
        assert not bad, f"{path}: 구조화 출력이 지원하지 않는 키워드 {sorted(bad)}"
        if "minItems" in node:
            assert node["minItems"] in (0, 1), f"{path}: minItems 는 0/1 만 된다"
        if node.get("type") == "object":
            props = node.get("properties") or {}
            assert node.get("additionalProperties") is False, \
                f"{path}: 객체마다 additionalProperties=false 가 필수다"
            assert "required" in node, f"{path}: 객체마다 required 가 필수다"
            assert set(node["required"]) == set(props), \
                f"{path}: required 가 properties 와 다르다 ({node['required']} vs {sorted(props)})"
            for k, v in props.items():
                _check_schema(v, f"{path}.{k}")
        if node.get("type") == "array" and isinstance(node.get("items"), dict):
            _check_schema(node["items"], f"{path}[]")
        for val in node.get("enum") or []:
            assert isinstance(val, (str, int, float, bool)) or val is None, \
                f"{path}: enum 에 복합 타입은 못 넣는다"

    FORBIDDEN_TOP = {"temperature", "top_p", "top_k", "output_format"}

    def _check_payload(name, body):
        """문서(api/messages + structured-outputs + thinking)와 대조."""
        assert set(body) == {"model", "max_tokens", "thinking", "system",
                             "messages", "output_config"}, f"{name}: 예상 밖 필드 {sorted(body)}"
        assert body["model"] == MODEL == "claude-sonnet-5", f"{name}: model"
        tail = body["model"].rsplit("-", 1)[-1]
        assert not (tail.isdigit() and len(tail) == 8), \
            f"{name}: 날짜 접미사(-20260401 같은 것)를 붙이면 안 된다"
        assert isinstance(body["max_tokens"], int) and 0 < body["max_tokens"] <= 128000, \
            f"{name}: max_tokens={body['max_tokens']}"
        assert body["thinking"] == {"type": "disabled"}, f"{name}: thinking"
        assert "budget_tokens" not in json.dumps(body), \
            f"{name}: budget_tokens 는 Sonnet 5 에서 400 이다"
        assert not (FORBIDDEN_TOP & set(body)), f"{name}: Sonnet 5 에서 400 나는 필드"
        assert isinstance(body["system"], str) and body["system"].strip(), f"{name}: system"
        msgs = body["messages"]
        assert isinstance(msgs, list) and len(msgs) == 1, f"{name}: messages"
        assert msgs[0]["role"] == "user", f"{name}: 첫 메시지는 user 여야 한다"
        assert isinstance(msgs[0]["content"], str) and msgs[0]["content"], f"{name}: content"
        json.loads(msgs[0]["content"])  # 우리가 넣은 것도 유효한 JSON 이어야 한다
        fmt = body["output_config"]["format"]
        assert set(body["output_config"]) == {"format"}, f"{name}: output_config"
        assert set(fmt) == {"type", "schema"}, f"{name}: format 필드 {sorted(fmt)}"
        assert fmt["type"] == "json_schema", f"{name}: format.type"
        _check_schema(fmt["schema"])
        # 바이트로 직렬화까지 되어야 실제로 보낼 수 있다.
        json.dumps(body, ensure_ascii=False).encode("utf-8")

    sent = []

    def _recording_post(payload, api_key):
        sent.append(payload)
        assert api_key == "sk-fake-test-key", "테스트 키가 아닌 값이 전송됐다"
        body = json.loads(payload["messages"][0]["content"])
        concern = body.get("concern")
        if concern == "news_title":
            data = {"cards": [{"id": "c_p_002", "title_ko": "가", "note": "나"}]}
        elif concern == "skill_note":
            data = {"cards": [{"id": "c_p_101", "note_ko": "다"}]}
        elif concern == "category":
            data = {"cards": [{"id": "c_p_101", "category": "기타"}]}
        elif concern == "keywords":
            data = {"keywords": []}
        else:
            data = {"cards": [], "briefing_ko": ["1", "2", "3"]}
        return _doc_response(data)

    def _doc_response(data, stop_reason="end_turn"):
        """문서(structured-outputs)가 보여주는 응답 모양 **그대로**.

        우리 파서에 맞춘 모양이 아니라, 문서의 예시 JSON 을 그대로 옮긴 것이다:
        JSON 은 text 블록 문자열이고 stop_reason 은 end_turn 이다.
        """
        return {
            "id": "msg_01XFDUDYJgAACzvnptvVoYEL",
            "type": "message",
            "role": "assistant",
            "model": MODEL,
            "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 2095, "output_tokens": 503},
        }

    payload_board = {
        "board_date": "2026-09-21",
        "generator": {"model": None},
        "sections": [
            {"id": "top_headlines", "title": "뉴스", "briefing_ko": [], "notes": [],
             "empty_reason": None,
             "cards": [
                 {"id": "c_p_001", "title": "국내 기사", "url": "https://example.com/kr1",
                  "sources": [{"name": "GeekNews"}], "region": "kr",
                  "dedup_key": "https://example.com/kr1", "summary_ko": None,
                  "title_ko": None, "note_ko": None},
                 {"id": "c_p_002", "title": "Global story", "url": "https://example.com/g1",
                  "sources": [{"name": "Techmeme"}], "region": "global",
                  "dedup_key": "https://example.com/g1", "summary_ko": None,
                  "title_ko": None, "note_ko": None},
             ]},
            {"id": "github_skills", "title": GITHUB_SECTION_TITLE, "briefing_ko": [],
             "notes": [], "empty_reason": None,
             "cards": [
                 {"id": "c_p_101", "repo": "acme/thing", "url": "https://github.com/acme/thing",
                  "desc": "Does a thing", "kind": "스킬", "category": "기타",
                  "title": "acme/thing", "sources": [{"name": "GitHub"}],
                  "summary_ko": None, "note_ko": None},
             ]},
            {"id": "keywords", "title": "오늘의 키워드", "briefing_ko": [], "notes": [],
             "empty_reason": None,
             "cards": [
                 {"id": "k_p_001", "keyword": "gpt6", "keyword_ko": None, "mentions": 2,
                  "source_count": 2, "change": "new", "dedup_key": "gpt6",
                  "items": [
                      {"title": "GPT-6 leaks", "url": "https://example.com/a", "source": "TC"},
                      {"title": "지피티6 정리", "url": "https://example.com/b", "source": "GN"},
                  ]},
             ]},
        ],
    }

    # 아래 6)에서도 이 보드를 쓴다. 4)가 제자리에서 바꿔버리므로 깨끗한 사본을 떠둔다.
    _PRISTINE_BOARD = json.dumps(payload_board, ensure_ascii=False)

    orig_post = globals()["_post"]
    orig_news_path = globals()["_NEWS_NOTES_PATH"]
    orig_skill_path = globals()["_SKILL_NOTES_PATH"]
    globals()["_post"] = _recording_post
    globals()["_NEWS_NOTES_PATH"] = os.path.join(SCRATCH, "summarize-payload-news.json")
    globals()["_SKILL_NOTES_PATH"] = os.path.join(SCRATCH, "summarize-payload-skill.json")
    try:
        summarize_board(payload_board, {"ANTHROPIC_API_KEY": "sk-fake-test-key"},
                        Budget(os.path.join(SCRATCH, "summarize-payload-budget.json")))
    finally:
        globals()["_post"] = orig_post
        globals()["_NEWS_NOTES_PATH"] = orig_news_path
        globals()["_SKILL_NOTES_PATH"] = orig_skill_path

    # 관심사 0 은 "카드가 있는 섹션마다" 한 번이다(여기선 뉴스·GitHub 둘).
    # 나머지 넷은 각각 한 번. 그래서 2 + 4 = 6.
    assert len(sent) == 6, f"요청이 6건이어야 한다 (실제 {len(sent)})"
    for i, body in enumerate(sent, 1):
        _check_payload(f"요청 {i}", body)
        user = json.loads(body["messages"][0]["content"])
        kind = user.get("concern") or f"section={user.get('section')!r}"
        print(f"  [{i}] {kind}  max_tokens={body['max_tokens']}  "
              f"system={len(body['system'])}자  user={len(body['messages'][0]['content'])}자  "
              f"schema_keys={sorted(body['output_config']['format']['schema']['properties'])}")
    print("  전송 본문 전문(첫 번째):")
    print("    " + json.dumps(sent[0], ensure_ascii=False, indent=2).replace("\n", "\n    ")[:1400]
          + "\n    …(생략)")
    print(f"  헤더: x-api-key / anthropic-version: {ANTHROPIC_VERSION} / content-type: "
          "application/json  (anthropic-beta 없음 — 구조화 출력은 정식 기능)")

    # -----------------------------------------------------------------------
    # 5) 문서가 적어둔 응답 모양 그대로를 먹여서, 우리 파서가 읽는지 본다.
    # -----------------------------------------------------------------------
    print("\n=== 5) 문서의 응답 모양 그대로 → 파서 확인 ===")
    doc_ok = _doc_response({"cards": [{"id": "x", "summary_ko": "가"}],
                            "briefing_ko": ["1", "2", "3"]})
    parsed, reason = _extract_json_with_reason(doc_ok)
    assert reason is None and parsed["cards"][0]["id"] == "x", (parsed, reason)
    print(f"  end_turn + text 블록 → 파싱 성공: {parsed}")

    parsed, reason = _extract_json_with_reason(
        _doc_response({"cards": []}, stop_reason="max_tokens"))
    assert parsed is None and "max_tokens" in reason, (parsed, reason)
    print(f"  stop_reason=max_tokens → 거부: {reason}")

    refusal = _doc_response({}, stop_reason="refusal")
    refusal["content"] = []
    refusal["stop_details"] = {"type": "refusal", "category": "cyber",
                               "explanation": "테스트용"}
    parsed, reason = _extract_json_with_reason(refusal)
    assert parsed is None and "거절" in reason and "cyber" in reason, (parsed, reason)
    print(f"  stop_reason=refusal → 거부: {reason}")

    # 문서: 도구를 같이 쓰면 text 가 아닌 블록이 섞일 수 있다. 그래도 읽어야 한다.
    mixed = _doc_response({"cards": [], "briefing_ko": ["1", "2", "3"]})
    mixed["content"] = ([{"type": "tool_use", "id": "tu_1", "name": "noop", "input": {}}]
                        + mixed["content"])
    parsed, _ = _extract_json_with_reason(mixed)
    assert parsed is not None, "text 가 첫 블록이 아니면 못 읽는다"
    print("  text 가 첫 블록이 아니어도 읽음")

    # -----------------------------------------------------------------------
    # 6) 오류 경로. 400/401 은 즉시 전체 중단, 429 는 한 번 기다렸다 재시도 후 중단.
    # -----------------------------------------------------------------------
    print("\n=== 6) HTTP 오류 → 정직하게 멈추는지 ===")
    import email.message

    def _http_error(code, retry_after=None):
        hdrs = email.message.Message()
        if retry_after is not None:
            hdrs["retry-after"] = str(retry_after)
        return urllib.error.HTTPError("https://api.anthropic.com/v1/messages",
                                      code, "boom", hdrs, None)

    def _error_board():
        return json.loads(_PRISTINE_BOARD)

    for code, expect, calls in ((401, "유효하지 않습니다", 1), (400, "요청이 거부됐습니다", 1),
                                (404, "찾을 수 없습니다", 1)):
        tries = []

        def _failing_post(payload, api_key, _code=code):
            tries.append(_code)
            raise _http_error(_code)

        globals()["_post"] = _failing_post
        try:
            b = _error_board()
            bud = Budget(os.path.join(SCRATCH, f"summarize-err-{code}.json"))
            bud.counts = {}
            err_notes = summarize_board(b, {"ANTHROPIC_API_KEY": "sk-fake-test-key"}, bud)
        finally:
            globals()["_post"] = orig_post
        assert len(tries) == calls, f"{code}: 재시도하면 안 되는데 {len(tries)}번 보냈다"
        assert any(expect in n for n in err_notes), (code, err_notes)
        assert any("이후 요약을 건너뜁니다" in n for n in err_notes), (code, err_notes)
        assert bud.counts.get("anthropic") == calls, (code, bud.counts)
        gh = [s for s in b["sections"] if s["id"] == "github_skills"][0]
        assert any("요약 호출이 중단되어" in n for n in gh["notes"]), gh["notes"]
        print(f"  {code}: 1회만 보내고 전체 중단. 노트 → {err_notes[0]}")

    slept = []
    tries429 = []

    def _rate_limited_post(payload, api_key):
        tries429.append(1)
        raise _http_error(429, retry_after=120)   # 상한(30초)에 걸려야 한다

    globals()["_post"] = _rate_limited_post
    orig_sleep = time.sleep
    time.sleep = lambda s: slept.append(s)
    try:
        b = _error_board()
        bud = Budget(os.path.join(SCRATCH, "summarize-err-429.json"))
        bud.counts = {}
        err_notes = summarize_board(b, {"ANTHROPIC_API_KEY": "sk-fake-test-key"}, bud)
    finally:
        time.sleep = orig_sleep
        globals()["_post"] = orig_post

    assert len(tries429) == RETRY_ATTEMPTS, f"429 는 {RETRY_ATTEMPTS}번만 보내야 한다 ({len(tries429)})"
    assert slept == [RETRY_WAIT_CAP], f"retry-after 상한이 안 먹었다: {slept}"
    assert bud.counts.get("anthropic") == RETRY_ATTEMPTS, bud.counts
    assert any("429" in n and "이후 요약을 건너뜁니다" in n for n in err_notes), err_notes
    kw = [s for s in b["sections"] if s["id"] == "keywords"][0]
    assert any("요약 호출이 중단되어" in n for n in kw["notes"]), kw["notes"]
    assert b["generator"]["model"] is None, "아무것도 못 채웠는데 model 이 찍혔다"
    print(f"  429: {RETRY_ATTEMPTS}번(재시도 1회, {slept[0]}초 대기) 뒤 전체 중단. "
          f"노트 → {err_notes[0]}")

    # 예산이 막히면 여전히 한 번도 안 보낸다 (fail-closed 유지).
    class _BlockedBudget:
        counts = {}

        def check(self, key, n=1):
            raise BudgetExceeded(f"{key}: 60/60 도달")

        def spend(self, key, n=1):
            raise AssertionError("예산이 막혔는데 호출했다")

    def _must_not_post(payload, api_key):
        raise AssertionError("예산이 막혔는데 전송했다")

    globals()["_post"] = _must_not_post
    try:
        b = _error_board()
        blocked_notes = summarize_board(b, {"ANTHROPIC_API_KEY": "sk-fake-test-key"},
                                        _BlockedBudget())
    finally:
        globals()["_post"] = orig_post
    assert any("예산" in n for n in blocked_notes), blocked_notes
    gh = [s for s in b["sections"] if s["id"] == "github_skills"][0]
    assert any("하루 호출 예산이 다 되어" in n for n in gh["notes"]), gh["notes"]
    print(f"  예산 차단: 한 번도 안 보냄. 노트 → {blocked_notes[0]}")

    # -----------------------------------------------------------------------
    # 7) 카드가 아주 많은 섹션 — 한 요청 한도를 지키는지.
    # -----------------------------------------------------------------------
    print("\n=== 7) 카드 폭주(1,160장) → 한 요청 한도 ===")
    big_sent = []

    def _big_post(payload, api_key):
        big_sent.append(payload)
        return _doc_response({"cards": [], "briefing_ko": ["1", "2", "3"]})

    big_board = {
        "board_date": "2026-09-21", "generator": {"model": None},
        "sections": [{
            "id": "github_skills", "title": GITHUB_SECTION_TITLE, "briefing_ko": [],
            "notes": [], "empty_reason": None,
            "cards": [{"id": f"c_big_{i:04d}", "repo": f"acme/r{i}", "kind": "스킬",
                       "url": f"https://github.com/acme/r{i}", "desc": "x" * 80,
                       "title": f"acme/r{i}", "sources": [{"name": "GitHub"}],
                       "category": "기타", "summary_ko": None, "note_ko": None}
                      for i in range(1160)],
        }],
    }
    globals()["_post"] = _big_post
    globals()["_SKILL_NOTES_PATH"] = os.path.join(SCRATCH, "summarize-big-skill.json")
    try:
        summarize_board(big_board, {"ANTHROPIC_API_KEY": "sk-fake-test-key"},
                        Budget(os.path.join(SCRATCH, "summarize-big-budget.json")))
    finally:
        globals()["_post"] = orig_post
        globals()["_SKILL_NOTES_PATH"] = orig_skill_path

    assert len(big_sent) == 3, f"섹션 하나에 관심사 셋 = 요청 셋 (실제 {len(big_sent)})"
    for body in big_sent:
        user = json.loads(body["messages"][0]["content"])
        assert len(user["cards"]) <= MAX_CARDS_PER_REQUEST, len(user["cards"])
        assert body["max_tokens"] <= MAX_TOKENS_CAP
    sec = big_board["sections"][0]
    assert any("앞의 40장만" in n for n in sec["notes"]), sec["notes"]
    print(f"  요청 {len(big_sent)}건, 카드 "
          f"{[len(json.loads(b['messages'][0]['content'])['cards']) for b in big_sent]}장, "
          f"max_tokens {[b['max_tokens'] for b in big_sent]}")
    for n in sec["notes"]:
        print(f"    노트: {n}")

    print("\n모든 검증 통과.")
