"""summarize.py 가 **실제 Anthropic API 계약**을 지키는지 본다.

`python tests/test_summarize.py` 로 돌린다. 외부 호출은 하지 않는다 —
`_post` 하나만 갈아끼우면 나머지 전부가 검증된다.

test_coverage.py 가 아니라 이 파일에 둔 이유: 작업 시점에 그 파일을 다른 사람이
고치고 있었다.

여기서 지키려는 것은 "코드가 돌아간다"가 아니라 **문서가 말하는 요청을 보내는가**이다.
이 모듈은 실제 API 에 한 번도 나가본 적이 없어서(키가 없다) 형식이 틀려도 아무도
모른 채 지나갔다. 그래서 각 테스트는 문서 근거를 주석에 남긴다.

문서 (2026-09-21 확인):
  - models/overview          : claude-sonnet-5 가 현재 유효한 ID
  - build-with-claude/structured-outputs : output_config.format / 스키마 부분집합 /
                               응답은 text 블록, stop_reason=end_turn, 베타 헤더 불필요
  - build-with-claude/thinking : Sonnet 5 는 thinking 을 끌 수 있다. budget_tokens 는 400
  - api/messages             : 필수 헤더와 필수 본문 필드
  - api/errors               : 어떤 상태코드가 재시도 대상인가
"""

import email.message
import json
import os
import sys
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from src import summarize as S                                   # noqa: E402
from src.budget import Budget, BudgetExceeded                    # noqa: E402

SCRATCH = os.environ.get("CLAUDE_SCRATCHPAD") or os.path.join(ROOT, "state")
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    mark = "  ok" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f"  — {detail}" if detail and not cond else ""))


def budget(tag):
    b = Budget(os.path.join(SCRATCH, f"test-summarize-{tag}.json"))
    b.counts = {}            # 이전 실행의 카운트를 물려받지 않는다
    return b


def doc_response(data, stop_reason="end_turn", stop_details=None):
    """문서(structured-outputs)의 응답 예시 **그대로**.

    우리 파서에 맞춘 모양이 아니다. 문서가 보여주는 필드 이름과 중첩을 옮긴 것이다:
    JSON 은 content 안 text 블록의 문자열이고, 성공하면 stop_reason 은 end_turn 이다.
    """
    body = {
        "id": "msg_01XFDUDYJgAACzvnptvVoYEL",
        "type": "message",
        "role": "assistant",
        "model": S.MODEL,
        "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 2095, "output_tokens": 503},
    }
    if stop_details is not None:
        body["stop_details"] = stop_details
    return body


def http_error(code, retry_after=None):
    hdrs = email.message.Message()
    if retry_after is not None:
        hdrs["retry-after"] = str(retry_after)
    return urllib.error.HTTPError("https://api.anthropic.com/v1/messages",
                                  code, "boom", hdrs, None)


def sample_board(github_cards=2):
    return {
        "board_date": "2026-09-21",
        "generator": {"model": None},
        "sections": [
            {"id": "top_headlines", "title": "뉴스", "briefing_ko": [], "notes": [],
             "empty_reason": None,
             "cards": [
                 {"id": "c_1", "title": "Global story", "url": "https://example.com/g1",
                  "sources": [{"name": "Techmeme"}], "region": "global",
                  "dedup_key": "https://example.com/g1",
                  "summary_ko": None, "title_ko": None, "note_ko": None},
                 {"id": "c_2", "title": "국내 기사", "url": "https://example.com/kr1",
                  "sources": [{"name": "GeekNews"}], "region": "kr",
                  "dedup_key": "https://example.com/kr1",
                  "summary_ko": None, "title_ko": None, "note_ko": None},
             ]},
            {"id": "github_skills", "title": S.GITHUB_SECTION_TITLE, "briefing_ko": [],
             "notes": [], "empty_reason": None,
             "cards": [
                 {"id": f"c_g{i}", "repo": f"acme/r{i}", "kind": "스킬",
                  "url": f"https://github.com/acme/r{i}", "desc": "Does a thing",
                  "title": f"acme/r{i}", "sources": [{"name": "GitHub"}],
                  "category": "기타", "summary_ko": None, "note_ko": None}
                 for i in range(github_cards)
             ]},
            {"id": "keywords", "title": "오늘의 키워드", "briefing_ko": [], "notes": [],
             "empty_reason": None,
             "cards": [
                 {"id": "k_1", "keyword": "gpt6", "keyword_ko": None, "mentions": 2,
                  "source_count": 2, "change": "new", "dedup_key": "gpt6",
                  "items": [
                      {"title": "GPT-6 leaks", "url": "https://example.com/a",
                       "source": "TC"},
                      {"title": "지피티6 정리", "url": "https://example.com/b",
                       "source": "GN"},
                  ]},
             ]},
        ],
    }


def run_with(post, board=None, bud=None, env=None):
    """`_post` 만 갈아끼우고 한 판 돌린다. 캐시 파일은 스크래치로 돌린다."""
    board = board if board is not None else sample_board()
    bud = bud if bud is not None else budget("run")
    saved = (S._post, S._NEWS_NOTES_PATH, S._SKILL_NOTES_PATH)
    S._post = post
    S._NEWS_NOTES_PATH = os.path.join(SCRATCH, "test-summarize-news.json")
    S._SKILL_NOTES_PATH = os.path.join(SCRATCH, "test-summarize-skill.json")
    try:
        notes = S.summarize_board(board, env or {"ANTHROPIC_API_KEY": "sk-fake"}, bud)
    finally:
        S._post, S._NEWS_NOTES_PATH, S._SKILL_NOTES_PATH = saved
    return board, notes, bud


# ── 모델 ID ─────────────────────────────────────────────────────────────────
# 사고 가능성: 학습 시점 기억으로 날짜 접미사를 붙이면(claude-sonnet-5-20260401)
# 404 가 온다. 문서(models/overview)의 ID 는 접미사 없는 그대로가 정답이다.
check("MODEL 은 현재 유효한 ID 다 (claude-sonnet-5)",
      S.MODEL == "claude-sonnet-5", S.MODEL)
_tail = S.MODEL.rsplit("-", 1)[-1]
check("MODEL 에 날짜 접미사가 없다",
      not (_tail.isdigit() and len(_tail) == 8), S.MODEL)

# ── thinking ────────────────────────────────────────────────────────────────
# 문서: Sonnet 5 는 thinking 이 기본으로 켜져 있고 "끌 수 있다".
# budget_tokens 는 Sonnet 5 에서 제거된 필드라 보내면 400 이다.
check("thinking 은 disabled 한 가지 필드뿐이다",
      S.THINKING == {"type": "disabled"}, S.THINKING)
_probe = S._request_body_for("sys", S.RESPONSE_SCHEMA, {"x": 1}, 2048)
check("요청 본문에 budget_tokens 가 없다 (Sonnet 5 에서 400)",
      "budget_tokens" not in json.dumps(_probe))

# ── 요청 본문 ───────────────────────────────────────────────────────────────
SENT = []


def recording_post(payload, api_key):
    SENT.append(payload)
    body = json.loads(payload["messages"][0]["content"])
    concern = body.get("concern")
    if concern == "news_title":
        data = {"cards": [{"id": "c_1", "title_ko": "가", "note": "나"}]}
    elif concern == "skill_note":
        data = {"cards": [{"id": "c_g0", "note_ko": "다"}]}
    elif concern == "category":
        data = {"cards": [{"id": "c_g0", "category": "다이어그램"}]}
    elif concern == "keywords":
        data = {"keywords": [{"keyword": "GPT-6", "keyword_ko": "GPT-6",
                              "item_urls": ["https://example.com/a",
                                            "https://example.com/b"]}]}
    else:
        data = {"cards": [{"id": "c_1", "summary_ko": "요약"}],
                "briefing_ko": ["1", "2", "3"]}
    return doc_response(data)


ok_board, ok_notes, ok_budget = run_with(recording_post)

check("관심사마다 요청 하나 — 카드가 몇 장이든 카드별 호출은 없다",
      len(SENT) == 6, f"{len(SENT)}건")

ALLOWED_TOP = {"model", "max_tokens", "thinking", "system", "messages", "output_config"}
# 문서(api/errors): Sonnet 5 에서 temperature/top_p/top_k 는 400. output_format 은 폐기된 이름.
FORBIDDEN_TOP = {"temperature", "top_p", "top_k", "output_format", "tools", "tool_choice"}

_bad_fields = [sorted(set(p) - ALLOWED_TOP) for p in SENT if set(p) - ALLOWED_TOP]
check("요청 본문에 문서에 없는 필드가 없다", not _bad_fields, str(_bad_fields))
check("400 을 부르는 필드(temperature/top_p/top_k/output_format)가 없다",
      not any(FORBIDDEN_TOP & set(p) for p in SENT))
check("필수 필드 셋(model/max_tokens/messages)이 전부 있다",
      all({"model", "max_tokens", "messages"} <= set(p) for p in SENT))
check("첫 메시지는 user 다 (문서: 첫 메시지는 user)",
      all(p["messages"][0]["role"] == "user" for p in SENT))
check("messages 는 한 턴뿐이다 (assistant prefill 은 4.6+ 에서 400)",
      all(len(p["messages"]) == 1 for p in SENT))
check("본문이 UTF-8 로 직렬화된다",
      all(json.dumps(p, ensure_ascii=False).encode("utf-8") for p in SENT))
check("API 키가 본문에 섞여 들어가지 않는다",
      not any("sk-fake" in json.dumps(p, ensure_ascii=False) for p in SENT))
check("보낸 요청 어디에도 budget_tokens 가 없다",
      not any("budget_tokens" in json.dumps(p) for p in SENT))
check("보낸 요청의 thinking 이 전부 disabled 다",
      all(p["thinking"] == {"type": "disabled"} for p in SENT))

# 구조화 출력 철자. output_config.format = {"type": "json_schema", "schema": ...}
check("output_config.format.type 은 json_schema 다",
      all(p["output_config"]["format"]["type"] == "json_schema" for p in SENT))
check("format 의 필드는 type/schema 둘뿐이다",
      all(set(p["output_config"]["format"]) == {"type", "schema"} for p in SENT))
check("output_config 안에 format 말고 다른 게 없다",
      all(set(p["output_config"]) == {"format"} for p in SENT))

# ── JSON 스키마 부분집합 ────────────────────────────────────────────────────
# 문서가 "지원하지 않는다"고 못 박은 키워드들. 쓰면 400 이 온다.
UNSUPPORTED = {"minLength", "maxLength", "minimum", "maximum", "exclusiveMinimum",
               "exclusiveMaximum", "multipleOf", "maxItems", "uniqueItems",
               "patternProperties", "propertyNames", "if", "then", "else", "not"}


def schema_problems(node, path="schema"):
    out = []
    if not isinstance(node, dict):
        return [f"{path}: dict 가 아니다"]
    bad = UNSUPPORTED & set(node)
    if bad:
        out.append(f"{path}: 미지원 키워드 {sorted(bad)}")
    if "minItems" in node and node["minItems"] not in (0, 1):
        out.append(f"{path}: minItems 는 0/1 만 된다")
    if node.get("type") == "object":
        props = node.get("properties") or {}
        if node.get("additionalProperties") is not False:
            out.append(f"{path}: additionalProperties=false 가 빠졌다")
        if set(node.get("required") or []) != set(props):
            out.append(f"{path}: required 가 properties 와 다르다")
        for k, v in props.items():
            out += schema_problems(v, f"{path}.{k}")
    if node.get("type") == "array" and isinstance(node.get("items"), dict):
        out += schema_problems(node["items"], f"{path}[]")
    for val in node.get("enum") or []:
        if not (isinstance(val, (str, int, float, bool)) or val is None):
            out.append(f"{path}: enum 에 복합 타입")
    return out


for _name, _schema in (("카드 요약", S.RESPONSE_SCHEMA),
                       ("해외 뉴스 제목", S.NEWS_TITLE_SCHEMA),
                       ("스킬 노트", S.SKILL_NOTE_SCHEMA),
                       ("부문 분류", S.CATEGORY_SCHEMA),
                       ("오늘의 키워드", S.KEYWORD_SCHEMA)):
    _probs = schema_problems(_schema)
    check(f"{_name} 스키마가 구조화 출력 부분집합 안에 있다", not _probs, "; ".join(_probs))

# 부문 enum 은 github_skills.py 의 표와 같은 이름만 쓴다(목록 밖 이름을 만들지 않게).
_enum = S.CATEGORY_SCHEMA["properties"]["cards"]["items"]["properties"]["category"]["enum"]
check("부문 enum 이 ALL_CATEGORIES 와 정확히 같다",
      list(_enum) == list(S.ALL_CATEGORIES))

# ── max_tokens ──────────────────────────────────────────────────────────────
# 사고: 예전 값 1024 는 "섹션당 카드 5장"을 전제한 숫자였는데, 실제 보드의
# github_skills 섹션에는 카드가 1,000장 넘게 있다. 카드 45장에 한국어 한 줄씩만
# 써도 출력이 3,000 토큰을 넘어 매번 max_tokens 에 잘렸고, 잘린 JSON 은 반드시
# 파싱에 실패한다 — 돈은 내고 결과는 0.
check("max_tokens 가 카드 수에 따라 커진다",
      S._max_tokens_for(40) > S._max_tokens_for(5) > S._max_tokens_for(0))
check("max_tokens 가 상한을 넘지 않는다",
      S._max_tokens_for(100000) == S.MAX_TOKENS_CAP)
check("max_tokens 가 옛날 값(1024)보다 항상 크다",
      S._max_tokens_for(0) > 1024, str(S._max_tokens_for(0)))
check("보낸 요청의 max_tokens 가 전부 유효 범위다 (0 < n <= 128000)",
      all(isinstance(p["max_tokens"], int) and 0 < p["max_tokens"] <= 128000
          for p in SENT))

# ── 응답 파싱 ───────────────────────────────────────────────────────────────
# 문서가 적어둔 모양 그대로를 먹인다. 우리가 지어낸 모양이 아니다.
_parsed, _reason = S._extract_json_with_reason(
    doc_response({"cards": [{"id": "x", "summary_ko": "가"}], "briefing_ko": ["1", "2", "3"]}))
check("문서의 응답 모양(text 블록 + end_turn)을 읽는다",
      _reason is None and _parsed["cards"][0]["id"] == "x", f"{_parsed} / {_reason}")

_parsed, _reason = S._extract_json_with_reason(
    doc_response({"cards": []}, stop_reason="max_tokens"))
check("stop_reason=max_tokens 는 거부한다 (잘린 JSON 을 믿지 않는다)",
      _parsed is None and "max_tokens" in (_reason or ""), str(_reason))

_refusal = doc_response({}, stop_reason="refusal",
                        stop_details={"type": "refusal", "category": "cyber",
                                      "explanation": "테스트"})
_refusal["content"] = []
_parsed, _reason = S._extract_json_with_reason(_refusal)
check("stop_reason=refusal 은 거부하고 분류를 노트에 남긴다",
      _parsed is None and "cyber" in (_reason or ""), str(_reason))

# 문서: 도구를 같이 쓰면 text 아닌 블록이 섞일 수 있다. 첫 블록만 보면 놓친다.
_mixed = doc_response({"cards": [], "briefing_ko": ["1", "2", "3"]})
_mixed["content"] = [{"type": "tool_use", "id": "tu", "name": "x", "input": {}}] + _mixed["content"]
check("text 가 첫 블록이 아니어도 읽는다",
      S._extract_json_with_reason(_mixed)[0] is not None)

check("응답이 JSON 이 아니면 조용히 None (예외를 흘리지 않는다)",
      S._extract_json({"content": [{"type": "text", "text": "깨진 {"}],
                       "stop_reason": "end_turn"}) is None)

# ── 결과 반영 ───────────────────────────────────────────────────────────────
_news = ok_board["sections"][0]
_gh = ok_board["sections"][1]
_kw = ok_board["sections"][2]
check("해외(global) 카드에만 한국어 제목이 붙는다",
      _news["cards"][0]["title_ko"] == "가" and not _news["cards"][1].get("title_ko"))
check("응답에 없던 카드는 손대지 않는다 (지어내지 않는다)",
      _news["cards"][1]["summary_ko"] is None)
check("부문이 목록 안 값으로 덮인다",
      _gh["cards"][0]["category"] == "다이어그램")
check("키워드 카드가 근거(item_urls) 둘 이상일 때만 만들어진다",
      len(_kw["cards"]) == 1 and _kw["cards"][0]["keyword"] == "GPT-6")
check("한 관심사라도 성공하면 generator.model 이 찍힌다",
      ok_board["generator"]["model"] == S.MODEL)

# 목록 밖 부문은 버린다 — 지어낸 부문보다 규칙 기반 추정치가 낫다.
_b = sample_board()


def _rogue_category_post(payload, api_key):
    body = json.loads(payload["messages"][0]["content"])
    if body.get("concern") == "category":
        return doc_response({"cards": [{"id": "c_g0", "category": "존재하지 않는 부문"}]})
    return recording_post(payload, api_key)


_b, _, _ = run_with(_rogue_category_post, board=_b, bud=budget("rogue"))
check("목록 밖 부문 이름은 버린다",
      _b["sections"][1]["cards"][0]["category"] == "기타")

# 목록에 없는 url 을 근거로 든 키워드는 버린다.
_b = sample_board()


def _rogue_url_post(payload, api_key):
    body = json.loads(payload["messages"][0]["content"])
    if body.get("concern") == "keywords":
        return doc_response({"keywords": [
            {"keyword": "X", "keyword_ko": "엑스",
             "item_urls": ["https://made-up.example/1", "https://made-up.example/2"]}]})
    return recording_post(payload, api_key)


_b, _, _ = run_with(_rogue_url_post, board=_b, bud=budget("rogueurl"))
check("목록에 없는 url 을 근거로 든 키워드는 버린다",
      _b["sections"][2]["cards"][0]["keyword"] == "gpt6")

# ── 오류 처리 ───────────────────────────────────────────────────────────────
# 사고: 예전에는 모든 예외가 "호출 실패 (HTTPError)" 한 줄이 되고, 실패해도 다음
# 관심사가 똑같이 두드렸다. 키가 틀리면(401) 그게 여섯 번 반복되고 429 면 막힌 문을
# 여섯 번 더 때린 뒤 보드는 아무 설명 없이 비어 있었다.
for _code, _phrase in ((401, "유효하지 않습니다"), (400, "요청이 거부됐습니다"),
                       (404, "찾을 수 없습니다"), (403, "권한이 없습니다"),
                       (413, "너무 큽니다")):
    _tries = []

    def _fail(payload, api_key, _c=_code):
        _tries.append(_c)
        raise http_error(_c)

    _bud = budget(f"err{_code}")
    _b, _notes, _bud = run_with(_fail, bud=_bud)
    check(f"{_code}: 한 번만 보내고 남은 관심사를 전부 멈춘다",
          len(_tries) == 1, f"{len(_tries)}번 보냄")
    check(f"{_code}: 무슨 일인지 한국어로 남긴다",
          any(_phrase in n for n in _notes) and
          any("이후 요약을 건너뜁니다" in n for n in _notes), str(_notes))
    check(f"{_code}: 쓴 예산이 보낸 횟수와 같다",
          _bud.counts.get("anthropic") == 1, str(_bud.counts))
    check(f"{_code}: 섹션에도 왜 비었는지 적힌다",
          any("요약 호출이 중단되어" in n for n in _b["sections"][1]["notes"]))

_tries, _slept = [], []


def _rate_limited(payload, api_key):
    _tries.append(1)
    raise http_error(429, retry_after=3600)     # 상한(30초)에 걸려야 한다


_orig_sleep = S.time.sleep
S.time.sleep = lambda s: _slept.append(s)
try:
    _b, _notes, _bud = run_with(_rate_limited, bud=budget("err429"))
finally:
    S.time.sleep = _orig_sleep

check("429 는 재시도 한 번까지만 한다",
      len(_tries) == S.RETRY_ATTEMPTS, f"{len(_tries)}번")
check("429 의 retry-after 는 존중하되 상한을 둔다 (한 시간 기다리지 않는다)",
      _slept == [S.RETRY_WAIT_CAP], str(_slept))
check("429 도 결국 남은 관심사를 멈춘다",
      any("429" in n and "이후 요약을 건너뜁니다" in n for n in _notes), str(_notes))
check("429: 재시도분까지 예산을 센다",
      _bud.counts.get("anthropic") == S.RETRY_ATTEMPTS, str(_bud.counts))
check("아무것도 못 채웠으면 generator.model 을 찍지 않는다",
      _b["generator"]["model"] is None)

# 529/5xx 도 재시도 대상이다 (문서: overloaded_error / api_error).
check("529 와 5xx 는 재시도 대상이다",
      {429, 500, 502, 503, 504, 529} <= S.RETRYABLE_STATUS)
check("4xx 중 재시도 대상은 408/409/429 뿐이다",
      {c for c in S.RETRYABLE_STATUS if 400 <= c < 500} == {408, 409, 429})

# ── 예산 fail-closed ────────────────────────────────────────────────────────
class BlockedBudget:
    counts = {}

    def check(self, key, n=1):
        raise BudgetExceeded(f"{key}: 60/60 도달")

    def spend(self, key, n=1):
        raise AssertionError("예산이 막혔는데 호출했다")


def _must_not_post(payload, api_key):
    raise AssertionError("예산이 막혔는데 전송했다")


_b, _notes, _ = run_with(_must_not_post, bud=BlockedBudget())
check("예산이 막히면 한 번도 보내지 않는다 (fail-closed 유지)",
      any("예산" in n for n in _notes), str(_notes))
check("예산으로 막혔다는 것도 섹션에 남는다",
      any("하루 호출 예산이 다 되어" in n for n in _b["sections"][1]["notes"]))

# ── 한 요청에 담는 카드 수 ──────────────────────────────────────────────────
# 사고 가능성: github_skills 섹션에는 카드가 1,000장 넘게 들어온다. 그대로 실으면
# 입력만 8만 토큰이고(관심사 셋이 같은 섹션을 본다) 출력은 감당이 안 된다.
_big = sample_board(github_cards=300)
_big_sent = []


def _big_post(payload, api_key):
    _big_sent.append(payload)
    return doc_response({"cards": [], "briefing_ko": ["1", "2", "3"]})


_big, _, _ = run_with(_big_post, board=_big, bud=budget("big"))
_counts = [len(json.loads(p["messages"][0]["content"]).get("cards") or [])
           for p in _big_sent]
check("한 요청에 카드를 한도 이상 담지 않는다",
      all(c <= S.MAX_CARDS_PER_REQUEST for c in _counts), str(_counts))
check("카드가 넘치면 몇 장만 채웠는지 섹션에 적는다",
      any("앞의" in n and "장만 채웠습니다" in n
          for n in _big["sections"][1]["notes"]))

# ── 키가 없을 때 ────────────────────────────────────────────────────────────
_noop_budget = budget("nokey")
check("키가 없으면 available() 이 False",
      S.available({}) is False and S.available({"ANTHROPIC_API_KEY": "x"}) is True)

_b = sample_board()
_before = json.dumps(_b, sort_keys=True, ensure_ascii=False)
_emit = S.EMIT_SECTION_NOTES
S.EMIT_SECTION_NOTES = False
try:
    _notes = S.summarize_board(_b, {}, _noop_budget)
finally:
    S.EMIT_SECTION_NOTES = _emit
check("키가 없고 EMIT_SECTION_NOTES=False 면 보드가 바이트 단위로 같다",
      json.dumps(_b, sort_keys=True, ensure_ascii=False) == _before)
check("키가 없으면 예산을 건드리지 않는다",
      _noop_budget.counts.get("anthropic") is None)
check("키가 없으면 노트 한 줄로 이유를 말한다",
      len(_notes) == 1 and "ANTHROPIC_API_KEY" in _notes[0])


def strip_notes(board):
    clone = json.loads(json.dumps(board, ensure_ascii=False))
    for sec in clone.get("sections") or []:
        sec.pop("notes", None)
    return json.dumps(clone, sort_keys=True, ensure_ascii=False)


_b2 = sample_board()
S.summarize_board(_b2, {}, _noop_budget)
check("키가 없을 때 달라지는 것은 섹션 notes 뿐이다 (카드는 한 글자도 안 바뀐다)",
      strip_notes(_b2) == strip_notes(json.loads(_before)))
_lines = [n for s in _b2["sections"] for n in (s.get("notes") or [])]
check("해외 뉴스 섹션이 '왜 한국어 제목이 없는지'를 말한다",
      any("한국어 제목이 없습니다" in n and "ANTHROPIC_API_KEY" in n for n in _lines),
      str(_lines))
check("GitHub 섹션이 '부문은 추정치'라고 말한다",
      any("규칙 기반 추정치" in n for n in _lines))
check("카드 요약이 비었다는 것도 섹션마다 말한다",
      any("한 줄 요약이 비어 있습니다" in n for n in _lines))

print(f"\n{len(PASS)} 통과 / {len(FAIL)} 실패")
if FAIL:
    print("실패:", ", ".join(FAIL))
raise SystemExit(1 if FAIL else 0)
