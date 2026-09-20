"""vendors / timeline / keywords / relevance / github_skills / board 검증.

`python tests/test_coverage.py` 로 돌린다. `tests/test_pipeline.py` 의 자매 파일이다 —
같은 규칙을 따른다: 각 테스트는 **실제로 났던 사고**를 지킨다. "함수가 뭔가 돌려준다"가
아니라 "이 사고가 다시 나면 여기서 잡힌다"가 기준이다. 사고 내용은 주석에 남긴다.

외부 호출을 하지 않는다. 네트워크를 쓰는 함수(_hf_latest, _hf_recent, _from_page,
weekly_delta 가 부르는 _get)는 테스트 안에서 손으로 만든 값을 돌려주는 함수로
잠깐 바꿔치기(monkeypatch)하고 끝나면 원래대로 되돌린다. state/ 아래 파일에
쓰는 함수(keywords.extract 의 이력 저장)는 경로를 tests/ 밑 임시 파일로 돌려서
프로젝트 상태를 건드리지 않는다.
"""

import os
import sys
import urllib.error
from datetime import datetime, timedelta, timezone
from email.message import Message

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from src import github_skills as gh_mod          # noqa: E402
from src import keywords as kw_mod               # noqa: E402
from src import relevance                        # noqa: E402
from src import timeline                         # noqa: E402
from src import vendors                          # noqa: E402
from src.board import build                      # noqa: E402

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    mark = "  ok" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f"  — {detail}" if detail and not cond else ""))


def news_item(title, url="https://x.com/1", source="TechCrunch",
              at=NOW, is_release=True):
    return dict(title=title, url=url, source_name=source,
                published_at=at, is_release=is_release)


def kw_item(title, source):
    return dict(title=title, source_name=source,
                url=f"https://x.com/{abs(hash((title, source))) % 999999}")


class NoopBudget:
    """weekly_delta 가 요구하는 최소 인터페이스. 진짜 Budget 은 state/ 에 쓴다."""

    def check(self, name):
        pass

    def spend(self, name):
        pass


# ═══════════════════════════════════════════════════════════════════════════
# vendors.py
# ═══════════════════════════════════════════════════════════════════════════

# 사고: Meta 회사 한 줄이 "마지막으로 낸 것" 기준이라, 더 최근에 나온
# 가드레일 분류기(Llama Guard)가 실제 Llama 4.2 출시보다 최신이라는 이유로
# 회사 대표 줄이 됐다. 계열별로 쪼개면(_family_rows) 버전 패턴이 없는
# 가드레일 글은 걸러지고 진짜 버전 출시가 남아야 한다.
meta_cands = [
    dict(name="Meta releases Llama Guard for content moderation",
         url="https://a", at=NOW, via="Meta"),                    # 더 최신이지만 버전 없음
    dict(name="Meta launches Llama 4.2",
         url="https://b", at=NOW - timedelta(days=11), via="Meta"),  # 더 오래됐지만 진짜 출시
]
meta_vendor = dict(id="meta", families=["Llama"], name="Meta", hf="meta-llama",
                   terms=["llama", "라마"])
meta_rows = vendors._family_rows(meta_vendor, meta_cands, NOW)
check("가드레일 분류기가 아니라 버전 출시가 대표 줄이 된다",
      len(meta_rows) == 1 and meta_rows[0]["headline"] == "Meta launches Llama 4.2",
      f"{meta_rows}")

# 사고: "Grok Bot now works with X" 같은 기능 소식이 계열명만 보고 출시로 잡혔다.
# 계열명 뒤에 (한 토큰 슬랙을 두고) 버전 숫자가 와야 한다.
check("계열명만 있고 버전이 없는 기능 소식은 출시가 아니다",
      not vendors._is_family_release("Grok Bot now works with X integration", "Grok"))
check("한 토큰 슬랙 허용 — Qwen-Image-2.1",
      vendors._is_family_release("Qwen-Image-2.1 released today", "Qwen"))
check("한 토큰 슬랙 허용 — Kimi-K3",
      vendors._is_family_release("Kimi-K3 launches", "Kimi"))

# 사고: "오픈AI ... 앤트로픽, 신형 모델 출시 검토" 가 두 회사 모두의 '최신 모델'로 올라갔다.
anthropic_vendor = next(v for v in vendors.VENDORS if v["id"] == "anthropic")
multi_vendor_item = news_item("오픈ai와 앤트로픽이 각각 신형 모델을 출시했다",
                              url="https://z", source="TechCrunch")
check("두 회사가 함께 언급된 헤드라인은 거부된다",
      vendors._mentions_many(multi_vendor_item["title"]))
check("업계 기사는 어느 회사의 출시로도 올라가지 않는다",
      vendors._from_items(anthropic_vendor, [multi_vendor_item]) is None)

# 사고: "앤트로픽, 신형 모델 출시 검토" 처럼 "검토"가 붙은 관측성 기사가 출시로 올라갔다.
review_item = news_item("앤트로픽, 신형 모델 출시 검토",
                        url="https://y", source="TechCrunch")
check("'검토'가 붙은 기사는 출시로 보지 않는다",
      vendors._from_items(anthropic_vendor, [review_item]) is None)

# 사고: 한 발표가 모델 둘을 실어서("Introducing Claude Fable 5.1 and Claude Mythos 5.1")
# 계열 두 줄이 제목 전체를 그대로 실은 나머지 똑같아 보였다. _model_name 이 계열 주변만
# 잘라내야 하고, 앞의 Introducing/Announcing 은 떼어내야 한다.
dual_title = "Introducing Claude Fable 5.1 and Claude Mythos 5.1"
check("모델 둘을 실은 발표에서 각 계열이 자기 이름만 남긴다",
      vendors._model_name(dual_title, "Fable") != vendors._model_name(dual_title, "Mythos"),
      f"{vendors._model_name(dual_title, 'Fable')!r} vs {vendors._model_name(dual_title, 'Mythos')!r}")
check("Introducing 은 모델명에서 떨어진다",
      vendors._model_name("Introducing Gemini 3.8", "Gemini") == "Gemini 3.8")

# 사고: "Premium seats are coming to ChatGPT Business" 라는 요금·좌석 공지가
# 다음 예정 모델로 잡혔다. 모델 신호가 없으면 예정으로 인정하지 않는다.
openai_vendor = next(v for v in vendors.VENDORS if v["id"] == "openai")
pricing_item = news_item("Premium seats are coming to ChatGPT Business",
                         url="https://p", source="OpenAI", is_release=False)
check("요금·좌석 공지는 '다음 모델 예정'이 아니다",
      vendors._next_expected(openai_vendor, [pricing_item]) is None)

# 사고: xAI 는 HF 에 뒤늦은 오픈웨이트(grok-2, 393일 전)만 있고 실제 최신(Grok 4.6)은
# 자기 뉴스 페이지에만 있다. 클로즈드 회사는 날짜가 더 옛날이어도 자기 채널이 이겨야 한다.
_fake_xai = dict(id="xai_test", families=[], name="xAI", hf="xai-org",
                 closed=True, page=None, terms=["grok"])
_orig_vendors_list = vendors.VENDORS
_orig_hf_latest = vendors._hf_latest
_orig_hf_recent = vendors._hf_recent
try:
    vendors.VENDORS = [_fake_xai]
    vendors._hf_latest = lambda author: dict(
        name="grok-2", url="https://huggingface.co/xai-org/grok-2",
        at=NOW - timedelta(days=1), via="Hugging Face")          # HF 가 더 최신 날짜
    vendors._hf_recent = lambda author, limit=25: []
    own_news = [news_item("xAI announces Grok 4.6", url="https://x.ai/news/grok-4-6",
                          source="xAI", at=NOW - timedelta(days=30))]  # 자기 발표는 더 옛날
    closed_rows, _ = vendors.vendor_status(own_news, now=NOW)
finally:
    vendors.VENDORS = _orig_vendors_list
    vendors._hf_latest = _orig_hf_latest
    vendors._hf_recent = _orig_hf_recent
check("클로즈드 회사는 날짜가 더 옛날이어도 자기 채널이 HF 를 이긴다",
      len(closed_rows) == 1 and closed_rows[0]["via"] == "xAI",
      f"{closed_rows}")


# ═══════════════════════════════════════════════════════════════════════════
# timeline.py
# ═══════════════════════════════════════════════════════════════════════════

# 사고: 같은 모델이 발표문(Qwen-Image-2.1)과 HF(Qwen/Qwen-Image-2.1) 양쪽으로 들어와
# 소유자 접두사 때문에 다른 점 두 개로 찍혔다. 접두사를 떼면 한 점이어야 한다.
# 동시에 작년 후보(Qwen-Old-1.0)는 올해 축에서 빠져야 한다.
_fake_qwen = dict(id="qwen_test", families=["Qwen"], name="Alibaba Qwen", hf="Qwen",
                  closed=False, page=None, terms=["qwen"])
_this_year_date = NOW - timedelta(days=5)
_last_year_date = datetime(NOW.year - 1, 12, 20, tzinfo=timezone.utc)
_orig_vendors_list = vendors.VENDORS
_orig_hf_recent = vendors._hf_recent
try:
    vendors.VENDORS = [_fake_qwen]
    vendors._hf_recent = lambda author, limit=25: (
        [dict(name="Qwen/Qwen-Image-2.1",
              url="https://huggingface.co/Qwen/Qwen-Image-2.1",
              at=_this_year_date, via="Hugging Face", channel="hf"),
         dict(name="Qwen/Qwen-Old-1.0",
              url="https://huggingface.co/Qwen/Qwen-Old-1.0",
              at=_last_year_date, via="Hugging Face", channel="hf")]
        if author == "Qwen" else [])
    feed_items = [news_item("Qwen-Image-2.1", url="https://example.com/qwen",
                            source="Alibaba", at=_this_year_date)]
    milestone, _ = timeline.build(feed_items, now=NOW)
finally:
    vendors.VENDORS = _orig_vendors_list
    vendors._hf_recent = _orig_hf_recent
check("소유자 접두사가 다른 같은 모델·같은 날은 점 하나로 합쳐진다",
      len(milestone["points"]) == 1,
      f"{milestone['points']}")
check("작년 후보는 올해 축에 오르지 않는다",
      all(p["date"].startswith(str(NOW.year)) for p in milestone["points"]),
      f"{milestone['points']}")


# ═══════════════════════════════════════════════════════════════════════════
# keywords.py
# ═══════════════════════════════════════════════════════════════════════════

_orig_hist_path = kw_mod.HISTORY_PATH
kw_mod.HISTORY_PATH = os.path.join(HERE, "_tmp_kw_history.json")
if os.path.exists(kw_mod.HISTORY_PATH):
    os.remove(kw_mod.HISTORY_PATH)

try:
    # 사고: "에이전트", "오픈", "companies" 같은 분야 이름·필드명이 오늘의 키워드로 떴다.
    field_name_items = [
        kw_item("에이전트 오픈소스 companies 협업툴 대규모 투자 유치", "A"),
        kw_item("에이전트 오픈소스 companies 협업툴 시리즈 B 투자", "B"),
        kw_item("에이전트 오픈소스 companies 협업툴 공개 베타 출시", "C"),
    ]
    field_rows, _ = kw_mod.extract(field_name_items, want=5, min_mentions=2)
    field_keys = {r["keyword"].lower() for r in field_rows}
    check("'에이전트'는 키워드로 뜨지 않는다", "에이전트" not in field_keys, f"{field_keys}")
    check("'오픈'은 키워드로 뜨지 않는다", "오픈" not in field_keys, f"{field_keys}")
    check("'companies'는 키워드로 뜨지 않는다", "companies" not in field_keys, f"{field_keys}")

    # 사고: 분야 이름을 걸러낸 다음에도 "researchers used" 같은 문장 조각이 남았다.
    fragments = kw_mod._phrases(
        "New study says researchers used AI models to detect cancer early")
    check("'researchers used' 같은 문장 조각은 주제가 아니다",
          "researchers used" not in [p.lower() for p in fragments],
          f"{fragments}")

    # 사고: 한 매체만 쓰는 말이 그 매체의 상용구인데도 키워드로 떴다.
    solo_items = [kw_item(f"블록체인 프로젝트 대규모 업데이트 {i}", "SoloOutlet")
                  for i in range(3)]
    solo_rows, _ = kw_mod.extract(solo_items, want=5, min_mentions=2)
    check("한 매체만 쓰는 말은 키워드가 되지 않는다",
          not any(r["keyword"] == "블록체인" for r in solo_rows),
          f"{solo_rows}")
finally:
    kw_mod.HISTORY_PATH = _orig_hist_path
    tmp_hist = os.path.join(HERE, "_tmp_kw_history.json")
    if os.path.exists(tmp_hist):
        os.remove(tmp_hist)
    tmp_hist_swap = tmp_hist + ".tmp"
    if os.path.exists(tmp_hist_swap):
        os.remove(tmp_hist_swap)


# ═══════════════════════════════════════════════════════════════════════════
# relevance.py
# ═══════════════════════════════════════════════════════════════════════════

# 사고: "ai" 가 said/chair/campaign/email/Thailand/available 속에서 오탐됐다.
check("'ai'가 단어 속에 있으면(said/chair/campaign/email) 관련도로 안 잡는다",
      not relevance.is_relevant(
          "The chair of the campaign said the email was sent by mistake", "geeknews"))
check("'ai'가 단어 속에 있으면(Thailand/available) 관련도로 안 잡는다",
      not relevance.is_relevant(
          "New species discovered in Thailand available for public viewing", "techmeme"))

# 사고: GeekNews 는 일반 테크 피드라 "언어 학습이 뇌 건강에 좋다"가 AI 뉴스로 올라갔다.
check("일반 피드의 AI 무관 기사(어학·뇌 건강)는 걸러진다",
      not relevance.is_relevant(
          "다른 언어를 배우는 것이 뇌 건강을 유지하는 가장 좋은 방법 중 하나일 수 있음",
          "geeknews"))

# 사고: TechCrunch AI 카테고리는 신뢰 소스라 바닥값을 받는데, 그 카테고리에 자기네
# 컨퍼런스 홍보("6 days left to get ahead at TechCrunch Disrupt 2026")가 섞여 뉴스 1위로 떴다.
# 신뢰 바닥값보다 광고 배제가 먼저 적용돼야 한다.
promo_title = "6 days left to get ahead at TechCrunch Disrupt 2026"
check("신뢰 소스의 자기 컨퍼런스 홍보는 광고로 표시된다", relevance.is_promo(promo_title))
check("광고 배제는 신뢰 소스 바닥값과 별개로 걸어야 실제로 걸러진다",
      relevance.is_promo(promo_title) and relevance.is_relevant(promo_title, "techcrunch_ai"),
      "run.py 는 is_relevant AND NOT is_promo 로 같이 걸러야 한다")

# 사고: 한글 조사가 AI 에 바로 붙는 경우(AI가/AI는)를 \b 기반 경계가 놓쳤다
# (\b 가 한글도 '단어 문자'로 쳐서 I 와 가 사이에 경계가 없다고 판단했다).
_ai_pat = relevance._compile_boundary("ai")
check("'AI가' 속의 ai 신호를 잡아낸다 (조사가 경계를 막지 않는다)",
      bool(_ai_pat.search("AI가 만든 그림이 대회에서 우승했다")))
check("'AI는' 속의 ai 신호를 잡아낸다",
      bool(_ai_pat.search("AI는 이제 일상이 됐다")))
check("반대로 영단어 속의 ai(said)는 여전히 걸러진다",
      not _ai_pat.search("The chair said thanks"))


# ═══════════════════════════════════════════════════════════════════════════
# github_skills.py
# ═══════════════════════════════════════════════════════════════════════════

# 사고: 레이트리밋(403, Remaining:0)과 "데이터 없음"을 둘 다 None 으로 뭉개서
# 섹션이 "응답이 없어 비어 있습니다"라고 거짓말을 했다. 실제로는 시간당 60회를 다 쓴 것이었다.
_orig_get = gh_mod._get


def _fake_get_rate_limited(url, token=None):
    hdrs = Message()
    hdrs["X-RateLimit-Remaining"] = "0"
    hdrs["X-RateLimit-Resource"] = "core"
    raise urllib.error.HTTPError(url, 403, "rate limited", hdrs, None)


try:
    gh_mod._get = _fake_get_rate_limited
    raised = False
    try:
        gh_mod.weekly_delta("octocat/hello-world", None, NoopBudget())
    except gh_mod.RateLimited:
        raised = True
    check("레이트리밋은 RateLimited 로 구분되고 조용히 None 이 되지 않는다", raised)
finally:
    gh_mod._get = _orig_get

try:
    gh_mod._get = lambda url, token=None: []
    empty_result = gh_mod.weekly_delta("octocat/hello-world", None, NoopBudget())
finally:
    gh_mod._get = _orig_get
check("진짜 데이터 없음은 여전히 None (RateLimited 와 구별됨)", empty_result is None)


# ═══════════════════════════════════════════════════════════════════════════
# board.py
# ═══════════════════════════════════════════════════════════════════════════

_board_tmp = os.path.join(HERE, "_tmp_boards_coverage")

# 사고: 섹션이 비면 사라지지 않고 이유를 남겨야 한다는 계약이 섹션마다 실제로
# 서로 다른 코드 경로(모델 업데이트는 vendor_rows 유무로 분기)를 탄다.
# 각 경로가 실제로 이유 문구를 남기는지 개별로 확인한다.
empty_board = build({}, [], [], {}, _board_tmp, NOW)
empty_map = {s["id"]: s for s in empty_board["sections"]}
check("뉴스 빈 섹션은 이유를 남긴다",
      empty_map["top_headlines"]["cards"] == []
      and empty_map["top_headlines"]["empty_reason"] == "수집된 항목이 없습니다.")
check("GitHub 빈 섹션은 이유를 남긴다",
      empty_map["github_skills"]["empty_reason"] == "GitHub 응답이 없어 오늘은 비어 있습니다.")
check("커뮤니티 빈 섹션은 이유를 남긴다",
      empty_map["communities"]["empty_reason"] == "커뮤니티 신호를 수집하지 못했습니다.")
check("키워드 빈 섹션은 이유를 남긴다",
      empty_map["keywords"]["empty_reason"] == "오늘 반복해서 나온 주제가 없습니다.")

# vendor_rows 를 아예 안 준 경우(None)와, 벤더 현황판이 돌았지만 빈 리스트를 돌려준
# 경우는 서로 다른 코드 경로다. 후자("현황을 가져오지 못했다")가 실제로 그 문구를 낸다.
vendor_empty_board = build({}, [], [], {}, _board_tmp, NOW, vendor_rows=[])
vendor_empty_map = {s["id"]: s for s in vendor_empty_board["sections"]}
check("벤더 현황을 못 가져온 경우 전용 이유를 남긴다 (일반 '새 모델 없음'과 다른 문구)",
      vendor_empty_map["model_updates"]["empty_reason"] == "벤더 현황을 가져오지 못했습니다.")

for _f in (os.path.join(_board_tmp, n) for n in ("latest.json",)):
    pass
if os.path.isdir(_board_tmp):
    for _f in os.listdir(_board_tmp):
        os.remove(os.path.join(_board_tmp, _f))
    os.rmdir(_board_tmp)


# ═══════════════════════════════════════════════════════════════════════════
# run.py — `--dry` 가드 (board.py 의 사고지만 실제 코드는 run.py 의 진입점에 있다)
# ═══════════════════════════════════════════════════════════════════════════

# 사고: `--dry` 모드에서 board_mod.write() 를 건너뛰는 코드를 빠뜨려서, 외부 호출을
# 안 하는 안전 모드가 멀쩡한 보드를 빈 보드로 덮어썼다. run.main() 은 실행하면
# 실제 예산 파일·상태 파일에 쓰기 때문에(순수 함수가 아닌 진입점) 여기서는 실행하지
# 않고, "dry 분기가 write 호출보다 먼저 return 한다"는 소스 구조만 정적으로 확인한다.
import inspect                                                    # noqa: E402

import run as run_mod                                             # noqa: E402

_main_src = inspect.getsource(run_mod.main)
_write_at = _main_src.index("board_mod.write(")
_last_dry_before_write = _main_src.rindex("if args.dry:", 0, _write_at)
_guard_segment = _main_src[_last_dry_before_write:_write_at]
check("--dry 분기는 board_mod.write() 호출보다 먼저 return 한다",
      "return" in _guard_segment,
      "write 앞의 dry 분기에 return 이 없다 — 빈 보드로 덮어쓸 수 있다")


print(f"\n{len(PASS)} 통과 / {len(FAIL)} 실패")
if FAIL:
    print("실패:", ", ".join(FAIL))
raise SystemExit(1 if FAIL else 0)
