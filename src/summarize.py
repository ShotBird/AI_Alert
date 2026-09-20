"""카드 한 줄 요약 + 섹션 3줄 브리핑. 티켓 05가 남긴 숙제(summary_ko/briefing_ko)를 채운다.

ANTHROPIC_API_KEY 가 없는 동안은 손댈 게 없다 — `available()` 이 False 를 돌려주고
`summarize_board()` 는 노트 하나 남기고 보드를 그대로 둔다. 키가 생기는 순간
run.py 를 바꾸지 않고도 이 모듈이 알아서 켜진다. 이 파일이 오늘 board.json 의
summary_ko: null / briefing_ko: [] 를 채우는 마지막 조각이다.

지켜야 할 것 셋:
  - **묶어서 호출한다.** 카드마다 부르지 않는다. 섹션 하나 = 요청 하나
    (카드 요약과 3줄 브리핑을 같은 요청에서 함께 받는다). 보드 전체로 봐도
    섹션 4개 중 카드가 있는 것만 부르니 하루 요청 수는 5회 안팎이다.
  - **지어내지 않는다.** 카드에는 제목·링크·출처 이름뿐이다. 본문을 읽은 것처럼
    구체적인 수치·스펙을 만들어내지 않는다. 모델에게도 그렇게 시키고,
    응답이 깨져 있거나 카드 하나가 빠져 있으면 그 카드의 summary_ko 는
    그냥 None 으로 남긴다 — 지어낸 요약보다 빈 칸이 정직하다.
  - **예산은 budget.check()/spend() 로만 나간다.** github_skills.py 와 같은 모양이다.
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


def summarize_board(board, env, budget):
    """board 를 제자리에서 채운다. 노트 목록을 돌려준다(메일/로그에 그대로 쓸 수 있게).

    키가 없으면 budget 은 건드리지도 않는다 — 호출 자체가 없으니 예산을 셀 이유가 없다.
    """
    api_key = _api_key(env)
    if not api_key:
        return ["ANTHROPIC_API_KEY가 없어 요약을 건너뜁니다. 키가 생기면 자동으로 채워집니다."]

    notes = []
    ran_any = False

    for section in board.get("sections") or []:
        cards = _summarizable_cards(section)
        if not cards:
            continue

        try:
            budget.check("anthropic")
        except (BudgetExceeded, BudgetUnavailable) as exc:
            notes.append(f"anthropic 예산 확인 실패, 이후 섹션 요약을 건너뜁니다: {exc}")
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

    print("\n=== 2) 가짜 전송으로 배치 요약 확인 ===")

    def _fake_post(payload, api_key):
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
    globals()["_post"] = _fake_post
    try:
        fake_board = {
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
                         "sources": [{"name": "Techmeme"}]},
                    ],
                },
                {
                    "id": "keywords", "title": "오늘의 키워드", "briefing_ko": [],
                    "empty_reason": "키워드 추출은 LLM 호출이 필요합니다.",
                    "cards": [],
                },
            ],
        }

        fake_budget = Budget(os.path.join(SCRATCH, "summarize-fake-budget.json"))
        fake_notes = summarize_board(fake_board, {"ANTHROPIC_API_KEY": "sk-fake-test-key"}, fake_budget)

        sec_model = fake_board["sections"][0]
        sec_news = fake_board["sections"][1]

        assert sec_model["cards"][0]["summary_ko"] == "온디바이스 추론 속도를 크게 끌어올렸다는 주장이다.", \
            sec_model["cards"][0]["summary_ko"]
        assert sec_model["cards"][1]["summary_ko"] is None, "응답에 없던 카드가 채워짐"
        assert len(sec_model["briefing_ko"]) == 3, sec_model["briefing_ko"]

        assert sec_news["cards"][0]["summary_ko"] is None, "깨진 응답인데 요약이 채워짐"
        assert sec_news["briefing_ko"] == [], "깨진 응답인데 브리핑이 채워짐"

        assert fake_board["generator"]["model"] == MODEL, "성공한 섹션이 있는데 model 이 안 찍힘"
        assert any("해석하지 못해" in n for n in fake_notes), fake_notes

        print(f"  카드 요약 반영: {sec_model['cards'][0]['summary_ko']!r}")
        print(f"  누락 카드는 None 유지: {sec_model['cards'][1]['summary_ko']!r}")
        print(f"  브리핑 3줄: {sec_model['briefing_ko']}")
        print(f"  깨진 응답 섹션은 그대로: summary_ko={sec_news['cards'][0]['summary_ko']!r}, "
              f"briefing_ko={sec_news['briefing_ko']!r}")
        print(f"  generator.model = {fake_board['generator']['model']!r}")
        print(f"  notes = {fake_notes}")
    finally:
        globals()["_post"] = orig_post

    print("\n모든 검증 통과.")
