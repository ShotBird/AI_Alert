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
import urllib.parse
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
from src import board as board_mod               # noqa: E402
from src import community as community_mod       # noqa: E402
from src import summarize as summarize_mod       # noqa: E402
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

# ── 다음 예정 칸 ─────────────────────────────────────────────────────────────
# 사고: 현황판의 '다음 예정'이 14줄 모두 "—" 였다. 2026-09-21 실측(수집 2,099건)에서
# 벤더 이름이 든 제목은 691건, 그중 앞날을 가리키는 말이 든 것은 4건뿐이었고 넷 다
# 업계 기사·좌석 요금·IPO 였다. 즉 오늘 피드에는 앞날의 모델 일정이 실제로 없다.
# 아래 테스트들은 "칸을 채워라"가 아니라 **채워질 때 제대로 채워지는가**를 지킨다.

# 사고: label 에 제목 전체가 들어갔다. 후보가 하나만 걸려도 좁은 표 한 칸에
# 기사 헤드라인이 통째로 들어간다 (web/index.html 의 nextCellHTML 은 이 값을
# <b> 로 감싸 날짜 자리에 넣는다). 칸에는 짧은 날짜·기간만 들어가야 하고,
# 헤드라인은 next_url 링크로만 닿아야 한다.
sched_item = news_item("오픈AI, 차기 GPT 모델 10월 15일 출시 예정",
                       url="https://s", source="AI타임스")
_sched = vendors._next_expected(openai_vendor, [sched_item], NOW)
check("다음 예정 라벨은 헤드라인이 아니라 짧은 날짜다",
      _sched and _sched["label"] == "10/15" and _sched["date"] == "2026-10-15",
      f"{_sched}")
check("헤드라인은 칸이 아니라 링크로만 닿는다",
      _sched and _sched["headline"] == sched_item["title"]
      and _sched["url"] == "https://s", f"{_sched}")

_q = vendors._next_expected(
    anthropic_vendor,
    [news_item("앤트로픽, 신형 클로드 모델 4분기 공개 예정",
               url="https://q", source="AI타임스")], NOW)
check("분기·연내 같은 기간도 한 칸에 들어가는 짧은 말로 실린다",
      _q and _q["label"] == "4분기" and _q["confidence"] == "예정", f"{_q}")

_own = vendors._next_expected(
    openai_vendor,
    [news_item("GPT-6 preview of the next model is coming on October 15",
               url="https://o", source="OpenAI")], NOW)
check("벤더 자기 채널에서 온 일정은 '확정'이다",
      _own and _own["confidence"] == "확정" and _own["label"] == "10/15", f"{_own}")

# 사고: 날짜가 없어도 후보가 되어, 예정 칸에 "…is expected to release a new model
# soon" 이라는 문장이 날짜인 척 들어갔다. 언제인지 못 말하면 적을 것이 없다.
check("언제인지 못 말하는 관측은 예정 칸에 올리지 않는다",
      vendors._next_expected(
          openai_vendor,
          [news_item("OpenAI is expected to release a new model soon",
                     url="https://n")], NOW) is None)

# 실측: AI타임스는 제목 앞에 "[9월18일]" 날짜 머리표를 단다. 예전 _pick_date 는
# 이걸 '09/18' 로 읽었다 — 지나간 날짜가 '다음 예정'으로 올라가면 오보다.
check("지나간 날짜는 '다음 예정'이 아니다",
      vendors._pick_when("[9월18일] 오픈AI서 드러난 셀프 프롬프트 인젝션", NOW) is None)

# 실측: 오늘 피드에 "March 20 ChatGPT outage" 가 실제로 있다. 영어 달 이름을
# 전치사 없이 날짜로 읽으면 3월 이전에 돌릴 때 '다음 예정 3/20' 이 된다.
check("전치사 없는 영어 달 이름은 일정으로 읽지 않는다",
      vendors._pick_when("March 20 ChatGPT outage: Here's what happened",
                         datetime(2026, 2, 1, tzinfo=timezone.utc)) is None)
check("on/by 가 붙으면 일정으로 읽는다",
      (vendors._pick_when("Shipping on October 15", NOW) or {}).get("label") == "10/15",
      f"{vendors._pick_when('Shipping on October 15', NOW)}")

# 실측: "Anthropic is planning to launch its IPO in November" 는 앞날 표현도,
# 모델 신호(launch)도, 읽히는 날짜(11월)도 다 갖췄다. FORWARD_WORDS 를 넓힌 뒤
# 이 기사가 4단계까지 올라온다 — 모델이 아니라는 판정이 마지막 방어선이다.
check("IPO 일정은 모델 예정이 아니다",
      vendors._next_expected(
          anthropic_vendor,
          [news_item("Anthropic is planning to launch its IPO in November",
                     url="https://i", source="Hacker News")], NOW) is None)

# 사고: OpenAI 피드 하나가 2015년치까지 1,210건을 준다. 현황판은 일부러 날짜 창을
# 쓰지 않으므로(마지막 갱신을 찾아야 한다) 예정도 그 전부를 훑었다. 창이 없으면
# 몇 년 전 글의 "coming soon" 이 오늘의 '다음 예정'이 된다.
check("오래된 기사의 '예정'은 계획이 아니라 역사다",
      vendors._next_expected(
          openai_vendor,
          [news_item("오픈AI, 차기 GPT 모델 10월 15일 출시 예정", url="https://s",
                     source="AI타임스", at=NOW - timedelta(days=200))], NOW) is None)

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
    closed_rows, closed_notes = vendors.vendor_status(own_news, now=NOW)
finally:
    vendors.VENDORS = _orig_vendors_list
    vendors._hf_latest = _orig_hf_latest
    vendors._hf_recent = _orig_hf_recent
check("클로즈드 회사는 날짜가 더 옛날이어도 자기 채널이 HF 를 이긴다",
      len(closed_rows) == 1 and closed_rows[0]["via"] == "xAI",
      f"{closed_rows}")

# 사용자 신고: "다음 예정일들이 하나도 안나와." 빈칸이 설명 없이 14줄 이어지면
# 수집이 고장 난 것처럼 보인다. 실제로는 피드에 앞날의 일정이 없는 날이 대부분이다.
check("다음 예정이 하나도 없으면 왜 비었는지 노트로 말한다",
      any("다음 예정" in n for n in closed_notes), f"{closed_notes}")


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


# ---------------------------------------------------------------------------
# 종류(kind) 축 — 사용자가 "Skill 과 MCP 를 구분하라"고 한 바로 그 축이다.
# ---------------------------------------------------------------------------

# 사고: 종류를 "어느 토픽으로 검색해 찾았나"로 정했다. 그 결과
#   - 설명에 "open-source MCP server"라고 적힌 feder-cr/AIHawk 가 `ai-agent`
#     토픽으로 먼저 걸려 "에이전트 프레임워크"가 됐고,
#   - 홍보용으로 `mcp` 태그만 달아둔 자바 면접 가이드(Snailclimb/JavaGuide)와
#     웹 UI(open-webui)가 "MCP 서버" 상위를 차지했다.
# 이제 검색 토픽이 아니라 레포 자신의 이름·설명·토픽으로 정한다.
check("설명이 'MCP server'라고 말하면 ai-agent 토픽으로 찾았어도 MCP 서버다",
      gh_mod._detect_kind(
          {"name": "AIHawk", "description": "Anti detect browser and web browsing "
                                            "agent: an open-source MCP server",
           "topics": ["ai-agent", "llm-agent", "browser"]},
          "에이전트 프레임워크") == "MCP 서버")
check("MCP 라고 말한 적 없는 자바 면접 가이드는 MCP 서버가 아니다",
      gh_mod._detect_kind(
          {"name": "JavaGuide", "description": "Java 면접 & 백엔드 면접 가이드",
           "topics": ["java", "interview", "mysql"]}, "스킬") != "MCP 서버")
# 사고: gemini-cli 는 `ai-agent` 토픽도 달고 있어서 프레임워크 규칙이 먼저 걸렸다.
# 이름에 cli 가 박힌 것이 더 강한 신호다.
check("이름이 -cli 로 끝나면 ai-agent 토픽이 있어도 CLI·개발도구다",
      gh_mod._detect_kind(
          {"name": "gemini-cli", "description": "An open-source AI agent in your terminal",
           "topics": ["ai-agent", "gemini"]}, "에이전트 프레임워크") == "CLI·개발도구")
check("agent-skills 토픽은 스킬로 간다 (MCP 와 섞이지 않는다)",
      gh_mod._detect_kind(
          {"name": "archify", "description": "Agent skill for architecture diagrams",
           "topics": ["agent-skills"]}, "CLI·개발도구") == "스킬")

# 사고: 레포 **이름**은 "JavaGuide"처럼 붙여 쓰기 때문에  가 걸리지 않아
# 모음집 필터를 통과했다. 이름은 경계 없는 별도 패턴으로 본다.
check("붙여 쓴 이름 속의 Guide 도 모음집으로 걸러진다",
      gh_mod._usable({"name": "JavaGuide", "description": "면접 지침 모음 for agents",
                      "topics": ["mcp"]})[0] is False)
check("guidance 처럼 guide 를 품지 않은 이름은 걸리지 않는다",
      gh_mod.NAME_COLLECTION_RE.search("guidance") is None)


# ---------------------------------------------------------------------------
# search 레이트리밋 — 여기서 CLI·개발도구 종류가 통째로 굶고 있었다
# ---------------------------------------------------------------------------

# 사고: 무인증 search 는 **분당 10회**다. 토픽 12개를 쉬지 않고 연달아 부르면
# 11번째부터 403 이 떨어져 마지막 두 토픽(llm-tools·ai-coding)이 통째로 빠졌다.
# 그 둘이 CLI·개발도구의 대부분이라, 그 종류만 스타 2,000 미만짜리로 채워졌다.
_slept = []
_clock = [0.0]
_pacer = gh_mod._Pacer(3, sleeper=_slept.append, clock=lambda: _clock[0])
for _ in range(3):
    _pacer.wait()
check("창 안에서 burst 까지는 기다리지 않는다", _slept == [])
_pacer.wait()
check("burst 를 넘기면 창이 열릴 때까지 기다린다 (403 을 맞기 전에 우리가 먼저 멈춘다)",
      len(_slept) == 1 and _slept[0] > 0, f"{_slept}")
_slept.clear()
_clock[0] = gh_mod.SEARCH_WINDOW + 1      # 창이 지나갔다
_pacer.wait()
check("창이 지나가면 다시 기다리지 않는다", _slept == [])


# ---------------------------------------------------------------------------
# top_rising — 부문별 20개 / 전체 Top 20 / 지어내지 않기
# ---------------------------------------------------------------------------

def _fake_repo(i, topic):
    """부문이 갈리도록 설명에 부문 단어를 심은 가짜 레포.

    종류는 설명이 아니라 토픽으로 갈리게 둔다 — 그래야 네 종류가 고루 나온다.
    """
    flavor = ["code review", "database", "terraform deploy"][i % 3]
    return {"full_name": f"o{i}/r{topic}{i}", "name": f"r{topic}{i}",
            "html_url": f"https://github.com/o{i}/r{topic}{i}",
            "description": f"Tool for {flavor}, works with any coding agent",
            "topics": [topic], "stargazers_count": 10000 - i,
            "pushed_at": "2026-09-20T00:00:00Z"}


_search_hits = []
_gap_hits = []
_NEEDLE = dict(gh_mod.CATEGORY_TABLE)
# 종류 어구 → 그 종류로 판정되는 **레포 자신의** 토픽.
_KIND_TOPIC = {"스킬": "agent-skills", "MCP 서버": "mcp-server",
               "에이전트 프레임워크": "ai-agent", "CLI·개발도구": "ai-cli"}
# 세상에 정말 몇 개 없는 니치. 실측한 것이다 — "cli agent legal contract" 는
# GitHub 전체에서 3건이다. 이런 칸은 짧은 채로 두고 이유를 노트에 적어야 한다.
_SCARCE_CAT = "법률·규정"
_SCARCE_TOTAL = 3
_gap_ids = {}


def _gap_repo(category, kind, i):
    """겨냥 질의가 돌려줄 법한 레포. 부문 단어와 종류 토픽을 심어 둔다.

    이름은 (부문, 종류, 순번)으로 **고정**한다 — 같은 칸에 질의를 두 번 던지면
    실제 GitHub 도 대체로 같은 레포를 돌려준다. 매번 새 이름을 주면 3건뿐인
    니치도 질의를 반복할수록 불어나, 테스트가 거짓으로 통과한다.
    """
    n = _gap_ids.setdefault((category, kind, i), len(_gap_ids) + 1)
    return {"full_name": f"gap{n}/p{n}", "name": f"p{n}",
            "html_url": f"https://github.com/gap{n}/p{n}",
            "description": f"agent tool for {_NEEDLE[category][0]} work",
            "topics": [_KIND_TOPIC[kind]], "stargazers_count": 500 - i,
            "pushed_at": "2026-09-20T00:00:00Z"}


def _parse_gap_query(query):
    """질의어를 (종류, 부문)으로 되돌린다. 실제 질의가 그 조합으로 만들어진다."""
    for kind, terms in gh_mod.KIND_TERMS.items():
        for kind_term in terms:
            if not query.startswith(kind_term + " "):
                continue
            rest = query[len(kind_term) + 1:]
            for category, cat_terms in gh_mod.CATEGORY_TERMS.items():
                if rest in cat_terms:
                    return kind, category
    return None, None


def _fake_search(url, token=None):
    if "/search/repositories" in url:
        query = urllib.parse.unquote(url.split("?q=", 1)[1].split("&", 1)[0])
        page = int(url.rsplit("&page=", 1)[1])
        if query.startswith("topic:"):
            topic = query[len("topic:"):]
            _search_hits.append((topic, page))
            if page > 1:
                return {"items": []}
            # CLI 계열만 얇게 준다 — 칸이 20개를 못 채우는 상황을 만들기 위해서다
            # (실제로 이 종류가 search 레이트리밋 때문에 굶고 있었다).
            # 토픽 목록은 늘어날 수 있으므로 KINDS 에서 읽는다 — 고정 목록으로 적어두면
            # 토픽을 하나 추가하는 순간 이 테스트가 조용히 무의미해진다.
            cli_topics = gh_mod.KINDS["CLI·개발도구"]
            n = 9 if topic == cli_topics[0] else (0 if topic in cli_topics else 60)
            return {"items": [_fake_repo(i, topic) for i in range(n)]}
        # 겨냥 질의(2단계). 1단계가 굶긴 칸을 여기서 판다.
        kind, category = _parse_gap_query(query)
        _gap_hits.append((kind, category, query))
        if kind is None:
            return {"items": [], "total_count": 0}
        if category == _SCARCE_CAT:
            return {"items": [_gap_repo(category, kind, i)
                              for i in range(_SCARCE_TOTAL)],
                    "total_count": _SCARCE_TOTAL}
        return {"items": [_gap_repo(category, kind, i) for i in range(25)],
                "total_count": 4000}
    # stargazers/history: 앞의 몇 개만 성공하고 그 뒤로는 한도 초과
    if len(_core_hits) >= 5:
        hdrs = Message()
        hdrs["X-RateLimit-Remaining"] = "0"
        hdrs["X-RateLimit-Resource"] = "core"
        raise urllib.error.HTTPError(url, 403, "rate limited", hdrs, None)
    _core_hits.append(url)
    return [{"week": 1, "total": 7}, {"week": 0, "total": 3}]


_core_hits = []
try:
    gh_mod._get = _fake_search
    _rows, _notes = gh_mod.top_rising(None, NoopBudget(), candidates=50, want=20,
                                      sleeper=lambda s: None, clock=lambda: 0.0,
                                      gap_requests=400)
finally:
    gh_mod._get = _orig_get

_pairs = {}
for _r in _rows:
    _pairs[(_r["kind"], _r["category"])] = _pairs.get((_r["kind"], _r["category"]), 0) + 1

# 사고: (종류, 부문) 칸마다 1~4개뿐이었다. 사용자가 두 번 말한 규칙은 "칸마다 20개".
check("칸(종류×부문)마다 최대 20개까지 담는다",
      _pairs and max(_pairs.values()) == 20, f"{_pairs}")
check("여러 칸이 20개를 채운다 (한 칸이 자리를 독식하지 않는다)",
      sum(1 for n in _pairs.values() if n == 20) >= 2, f"{_pairs}")

# 사고: 전체 목록의 맨 앞이 증가분을 잰 것이 아니라 누적 스타 큰 것이었다.
# "전체"는 전 부문을 한 풀에 넣고 증가분으로 줄 세운 Top 20 이어야 한다.
_measured = [r for r in _rows if r["stars_delta"] is not None]
check("잰 것이 전부 못 잰 것보다 앞에 온다 (전체 = 증가분 순)",
      all(r["stars_delta"] is not None for r in _rows[:len(_measured)]),
      f"{[r['stars_delta'] for r in _rows[:8]]}")
check("전체 Top 20 에 여러 부문이 들어간다",
      len({(r["kind"], r["category"]) for r in _rows[:20]}) >= 3)

# 사고: core 한도에 걸려 **한 건도 못 쟀는데** 노트는 "후보 45개 중 증가분을 구한 것
# 45개"라고 적었다. len(rows) 를 셌기 때문이다. 못 잰 줄은 stars_delta=None 으로
# 남아야 하고, 노트는 실제로 잰 수를 말해야 한다.
check("못 잰 줄은 증가분을 지어내지 않고 None 으로 남는다",
      any(r["stars_delta"] is None for r in _rows)
      and all(isinstance(r["stars_delta"], int) or r["stars_delta"] is None
              for r in _rows))
check("노트가 '실제로 잰 수'를 말한다 (행 수가 아니라)",
      any(f"{len(_rows)}개 중 {len(_measured)}개" in n for n in _notes),
      f"{_notes}")
check("core 한도에 걸린 사실을 노트로 밝힌다",
      any("core 한도" in n for n in _notes), f"{_notes}")
check("몇 칸이 20개를 채웠는지 노트가 숫자로 말한다",
      any("20개를 채웠습니다" in n for n in _notes), f"{_notes}")
# 사고 방지: 한 줄도 없는 칸은 per_cat 에 아예 안 나타난다. 그것만 세면 분모에서도
# 빠져서 "다 채웠다"로 읽힌다. 분모는 있을 수 있는 칸 전부(종류 4 × 부문 27)다.
check("노트의 분모는 '있는 칸'이 아니라 '있을 수 있는 칸 전부'다",
      any(f"/{len(gh_mod.KINDS) * len(gh_mod.CATEGORIES)}칸" in n for n in _notes),
      f"{_notes}")

# ---------------------------------------------------------------------------
# 칸 채우기(gap fill) — "얇은 칸"은 검색에 없어서가 아니라 안 물어봐서 얇았다
# ---------------------------------------------------------------------------
# 사고: 토픽 14개를 스타 순으로 훑고 끝냈다. 인기 부문은 넘치고 니치 부문
# (번역·법률·과학)은 0~3개였다. 실측해 보니 "mcp translation" 한 번이면 그 칸에
# 딱 맞는 후보가 25개 나왔다 — 우리 칸이 0개일 때. 질의를 안 던진 것이 원인이었다.
check("겨냥 질의는 (종류 어구 + 부문 어구)로 만들어진다",
      gh_mod._pair_queries("MCP 서버", "번역·언어")[0] == "mcp server translation",
      f"{gh_mod._pair_queries('MCP 서버', '번역·언어')[:2]}")
check("부문 표에 있는 모든 부문에 겨냥 질의가 있다 (기타만 예외)",
      all(gh_mod._pair_queries(k, c) for k in gh_mod.KINDS
          for c in gh_mod.CATEGORIES if c != "기타"),
      f"{[c for c in gh_mod.CATEGORIES if not gh_mod._pair_queries('스킬', c)]}")
check("'기타'는 겨냥하지 않는다 (아무것도 안 걸렸을 때의 값이라 검색어가 없다)",
      gh_mod._pair_queries("스킬", "기타") == [])

# 1단계가 준 부문은 셋뿐이다(code review / database / terraform deploy).
# 나머지 부문은 전부 2단계가 채운 것이어야 한다.
_stage1_cats = {"코드리뷰", "데이터베이스", "인프라·배포"}
_filled_by_gap = [k for k, n in _pairs.items() if k[1] not in _stage1_cats and n == 20]
check("1단계가 0개로 남긴 칸을 2단계가 20개까지 채운다",
      len(_filled_by_gap) >= 20, f"{len(_filled_by_gap)}칸")
check("2단계가 채운 칸의 부문 배지가 겨냥한 부문과 같다 (아무거나 밀어 넣지 않는다)",
      all(gh_mod._classify({"description": r["desc"], "topics": []}) == r["category"]
          for r in _rows), "부문 배지와 설명이 어긋난 줄이 있다")

# 사고 방지: 진짜로 없는 칸을 억지로 채우면 부문 배지가 거짓말이 된다.
# "cli agent legal contract" 는 GitHub 전체에서 3건이다. 짧게 두고 이유를 적는다.
_scarce_pairs = {k: n for k, n in _pairs.items() if k[1] == _SCARCE_CAT}
check("검색 결과가 3건뿐인 니치는 20개로 부풀리지 않는다",
      _scarce_pairs and max(_scarce_pairs.values()) <= _SCARCE_TOTAL,
      f"{_scarce_pairs}")
check("짧은 칸은 어느 부문이 왜 짧은지 건수와 함께 노트에 적는다",
      any(_SCARCE_CAT in n and f"{_SCARCE_TOTAL}건" in n for n in _notes),
      f"{_notes}")
check("겨냥 검색 횟수는 상한을 넘지 않는다",
      len(_gap_hits) <= 400, f"{len(_gap_hits)}")

# 사고: 페이서를 안 타는 두 번째 검색 경로가 생기면 11번째부터 403 을 먹는다.
# 1·2단계가 같은 _search/_Pacer 를 쓰는지 호출 수로 확인한다.
_paced = []
_paced_pacer = gh_mod._Pacer(2, sleeper=lambda s: _paced.append(s), clock=lambda: 0.0)
try:
    gh_mod._get = lambda url, token=None: {"items": [], "total_count": 0}
    for _ in range(4):
        gh_mod._search("mcp translation", None, NoopBudget(), [], _paced_pacer, "t")
finally:
    gh_mod._get = _orig_get
check("겨냥 검색도 페이서를 탄다 (403 을 맞기 전에 우리가 멈춘다)",
      len(_paced) == 2, f"{_paced}")

# 사고 방지: 질의 140개가 전부 403 이면 섹션 노트가 실패 목록 140줄이 된다.
# 화면에서 그건 설명이 아니라 고장으로 보인다. 연속 실패면 일찍 멈추고 한 줄로 적는다.
_flood_notes = []


def _always_403(url, token=None):
    hdrs = Message()
    hdrs["X-RateLimit-Remaining"] = "0"
    raise urllib.error.HTTPError(url, 403, "no", hdrs, None)


try:
    gh_mod._get = _always_403
    _flood_spent, _flood_ev = gh_mod._gap_fill(
        {}, [], set(), None, NoopBudget(), _flood_notes,
        gh_mod._Pacer(99, sleeper=lambda s: None, clock=lambda: 0.0),
        20, 140)
finally:
    gh_mod._get = _orig_get
check("검색이 계속 거절하면 일찍 멈춘다 (140번 두드리지 않는다)",
      _flood_spent <= 5, f"{_flood_spent}")
check("실패 140줄을 섹션 노트에 쏟지 않는다",
      len(_flood_notes) <= 2, f"{_flood_notes}")

# 사고: 403 이 떨어져도 그 칸은 개수가 그대로라 바로 다음 순번에 또 뽑혔고,
# 곧장 다시 두드려 그 칸의 질의 세 개를 연달아 403 으로 날렸다(실측 9회).
# 실패는 "더 빨리 다시 해보라"가 아니다.
_cool = []
_cool_pacer = gh_mod._Pacer(3, sleeper=_cool.append, clock=lambda: 0.0)
_cool_pacer.wait()
_cool_pacer.cooldown()
_cool_pacer.wait()
check("403 뒤에는 한 창을 쉬고 다시 두드린다",
      len(_cool) == 1 and _cool[0] > 0, f"{_cool}")

# 짧은 칸이라고 다 같은 이야기가 아니다. 셋을 섞어 "못 채웠습니다" 한 줄로 적으면
# 고칠 수 있는 것(분류)과 없는 것(세상에 없음)과 다음 회차 몫(예산)이 구별되지 않는다.
_A = ("스킬", "법률·규정")        # 겨냥해 봤더니 GitHub 전체가 3건 — 진짜 니치
_B = ("스킬", "백엔드·API")       # 후보는 4천 건인데 우리 규칙이 안 보냈다
_C = ("스킬", "과학·바이오")      # 아직 손도 못 댔다
_why = gh_mod._fill_notes({_A: 3, _B: 5, _C: 0, ("스킬", "보안"): 20},
                          {_A: 3, _B: 4000}, 20, 168, 5000)
check("진짜 니치는 건수를 들어 '없다'고 말한다",
      any("법률·규정 3건" in n for n in _why), f"{_why}")
check("후보는 많은데 분류가 못 보낸 칸은 따로 말한다",
      any("규칙 분류가" in n for n in _why), f"{_why}")
check("예산이 모자라 손 못 댄 칸은 '없다'가 아니라 '못 팠다'로 말한다",
      any("손대지 못했습니다" in n for n in _why), f"{_why}")


# ---------------------------------------------------------------------------
# 카드 크기 — 이 섹션만 스키마가 다르다
# ---------------------------------------------------------------------------
# 사고: 칸마다 20줄로 늘리자 이 섹션 하나가 latest.json 의 703KB 를 차지했다
# (보드 전체 1,074KB). 휴대폰이 매일 아침 내려받는 파일이다. 화면이 안 읽는
# 필드를 이 섹션에서만 뺀다.
check("설명은 160자를 넘지 않는다",
      gh_mod._row({"full_name": "o/r", "description": "가" * 400,
                   "stargazers_count": 1}, None)["desc"].__len__()
      <= gh_mod.DESC_MAX,
      "desc 가 안 잘렸다")
check("짧은 설명은 자르지 않는다 (말줄임표를 붙이지 않는다)",
      gh_mod._row({"full_name": "o/r", "description": "short one-liner",
                   "stargazers_count": 1}, None)["desc"] == "short one-liner")
check("title 은 싣지 않는다 (repo 와 글자까지 같았다)",
      "title" not in gh_mod._row({"full_name": "o/r", "description": "x",
                                  "stargazers_count": 1}, None))

_gh_card = board_mod._github_card(
    {"repo": "acme/thing", "url": "https://github.com/acme/thing", "desc": "x",
     "stars": 10, "stars_delta": None, "category": "보안", "kind": "스킬",
     "pushed_at": "2026-09-20"}, 7, "2026-09-21", {})
check("GitHub 카드는 화면이 읽는 필드만 싣는다",
      set(_gh_card) == set(board_mod.GITHUB_CARD_FIELDS), f"{sorted(_gh_card)}")
check("죽은 필드(heat·sources·dedup_key·change·published_at·title)는 빠진다",
      not ({"heat", "sources", "source_count", "dedup_key", "change",
            "published_at", "title"} & set(_gh_card)), f"{sorted(_gh_card)}")
# summarize.py 의 _summarizable_cards 가 `"summary_ko" in card` 로 고른다.
# 값이 None 이어도 **키는 남아야** 이 섹션이 요약에서 조용히 빠지지 않는다.
check("summary_ko 키는 값이 없어도 남는다 (요약 대상 판별에 쓰인다)",
      "summary_ko" in _gh_card and _gh_card["summary_ko"] is None)
check("id 는 남는다 (summarize.py 가 카드를 되짚는 열쇠다)",
      _gh_card["id"] == "c_2026-09-21_007")

# 사고: 측정 예산(core 60/시간)을 앞에서부터 쓰면 가장 큰 칸 하나가 다 먹고
# 나머지 칸은 한 줄도 못 쟀다. 칸을 한 바퀴 돌며 재야 "전 부문 포함"이 된다.
check("적은 측정 예산도 여러 칸에 나눠 쓴다",
      len({(r["kind"], r["category"]) for r in _measured}) >= 3,
      f"{[(r['kind'], r['category']) for r in _measured]}")


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

# 사고: 수집기들이 "왜 이 섹션이 이 모양인지"를 설명하는 notes 를 만들어 돌려주는데
# (github_skills 의 "부문 N곳이 20개를 못 채웠습니다", timeline 의 "최근 N건만
# 축에 올렸습니다" …) 보드에 섹션별 통로가 없어 전부 generator.notes 한 자루에
# 들어갔고, 그걸 그리는 화면이 없어 통째로 버려졌다. 사용자는 짧은 목록만 보고
# 이유는 못 봤다. 이제 섹션마다 제 몫이 실린다.
_gh_note = "부문 68/95곳이 20개를 못 채웠습니다"
_notes_board = build({}, [], [], {}, _board_tmp, NOW,
                     notes=["보드 전체 메모"],
                     section_notes={"github_skills": [_gh_note],
                                    "model_updates": ["올해 출시 93건 중 최근 40건만"]})
_notes_map = {s["id"]: s for s in _notes_board["sections"]}
check("섹션별 notes 가 그 섹션에 실린다 (generator.notes 로만 새지 않는다)",
      _notes_map["github_skills"]["notes"] == [_gh_note],
      f'{_notes_map["github_skills"]["notes"]}')
check("다른 섹션도 제 몫의 notes 를 받는다",
      _notes_map["model_updates"]["notes"] == ["올해 출시 93건 중 최근 40건만"])
check("섹션 notes 가 남의 섹션으로 번지지 않는다",
      _notes_map["top_headlines"]["notes"] == []
      and _gh_note not in _notes_map["communities"]["notes"])
check("보드 전체 notes 는 그대로 generator.notes 에 남는다 (기존 동작 유지)",
      _notes_board["generator"]["notes"] == ["보드 전체 메모"])
check("section_notes 를 안 줘도 모든 섹션에 notes 키가 있다 (화면이 undefined 를 안 본다)",
      all(isinstance(s.get("notes"), list) for s in empty_board["sections"]))

# 사고: 섹션 제목 문자열이 board.py 와 summarize.py 두 곳에 손으로 적혀 있어
# 한쪽만 고치면 조용히 갈라졌다. 이제 한 상수를 양쪽이 import 한다.
check("GitHub 섹션 제목은 한 상수에서 온다",
      board_mod.SECTION_TITLES["github_skills"] is board_mod.GITHUB_SECTION_TITLE
      and summarize_mod.GITHUB_SECTION_TITLE is board_mod.GITHUB_SECTION_TITLE)
# 사용자 지적: "GitHub급상승 << 이 아니라 GitHub Skill이었을텐데?"
check("제목이 '급상승'이 아니라 사용자가 말한 '스킬'을 쓴다",
      "급상승" not in board_mod.GITHUB_SECTION_TITLE
      and "스킬" in board_mod.GITHUB_SECTION_TITLE,
      board_mod.GITHUB_SECTION_TITLE)

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


# ═══════════════════════════════════════════════════════════════════════════
# community.py — 누적치를 활동으로 착각하지 않는다 (티켓 23, 2차 반려)
# ═══════════════════════════════════════════════════════════════════════════

# 사고: 커뮤니티 섹션이 디스코드 **누적 회원수**(approximate_member_count)를
# 신호 자리에 싣는 바람에, 사람이 거의 남지 않은 Midjourney 서버가 1,857만이라는
# 숫자로 매일 1위를 했다. 같은 실수가 국내에도 있었다 — 아카라이브 '구독자 수'
# 역시 누적이라, 2023년에 멈춘 채널과 글이 한 건도 없는 채널이 목록에 남아
# 있었다(게다가 그 둘은 구독자 0으로 표시됐다). 아래 테스트들은 그 두 사고가
# 다시 나면 잡는다. 네트워크는 쓰지 않는다 — _fetch_* 를 잠깐 바꿔치기한다.

import json as _json                                              # noqa: E402
import tempfile                                                   # noqa: E402

_com_orig = dict(
    fetch_discord=community_mod._fetch_discord,
    fetch_arca=community_mod._fetch_arca,
    fetch_discourse=community_mod._fetch_discourse,
    sleep=community_mod.time.sleep,
    urlopen=community_mod.urllib.request.urlopen,
)
community_mod.time.sleep = lambda *_a, **_k: None  # 예의상 두는 간격은 테스트에 불필요


class _ComBudget:
    """예산은 이 테스트의 관심사가 아니다 — 항상 통과시키고 횟수만 센다."""

    def __init__(self):
        self.counts = {}

    def check(self, key, n=1):
        return 999

    def spend(self, key, n=1):
        self.counts[key] = self.counts.get(key, 0) + n


def _com_cache():
    fd, path = tempfile.mkstemp(prefix="ai_alert_com_", suffix=".json", dir=HERE)
    os.close(fd)
    os.remove(path)  # 캐시가 없는 상태에서 시작해야 실제 조회 경로를 탄다
    return path


def _com_run(want=6, **fakes):
    """캐시를 매번 새로 만들어 top_communities 를 돌린다."""
    community_mod._fetch_discord = fakes.get(
        "discord", lambda code, budget, notes: (None, None, "error", "테스트"))
    community_mod._fetch_arca = fakes.get(
        "arca", lambda path, now=None: (None, "테스트", None))
    community_mod._fetch_discourse = fakes.get(
        "discourse", lambda api: (None, "테스트", None))
    path = _com_cache()
    try:
        return community_mod.top_communities([], _ComBudget(), path, want=want)
    finally:
        community_mod._fetch_discord = _com_orig["fetch_discord"]
        community_mod._fetch_arca = _com_orig["fetch_arca"]
        community_mod._fetch_discourse = _com_orig["fetch_discourse"]
        if os.path.exists(path):
            os.remove(path)


_com_now = datetime.now(timezone.utc)

# ── 사고 1: 누적 회원수가 신호 자리에 들어갔다 ───────────────────────────────
_rows, _notes = _com_run(
    discord=lambda code, budget, notes: (12_345, 18_570_000, "ok", None))
_dc = [r for r in _rows if r["signal_kind"] == "지금 접속"]
check("디스코드 행의 숫자는 접속자 수이지 누적 회원수가 아니다",
      _dc and all(r["signal_value"] == 12_345 for r in _dc),
      f"signal_value={[r['signal_value'] for r in _dc][:3]} — 누적치가 들어왔다")
check("누적 회원수는 note 에만, 접속 비율과 함께 남는다",
      _dc and "18,570,000" in (_dc[0]["note"] or "") and "%" in (_dc[0]["note"] or ""),
      f"note={_dc[0]['note'] if _dc else None}")

# ── 사고 2: 멈춘 채널이 목록에 남았다 ────────────────────────────────────────
# 마지막 글이 30일 전인 채널. 조회 자체는 성공했지만 커뮤니티가 아니다.
_rows, _notes = _com_run(
    arca=lambda path, now=None: (5, "최근 글 …", _com_now - timedelta(days=30)))
check("마지막 글이 오래된 아카라이브 채널은 목록에서 빠진다",
      not [r for r in _rows if r["id"].startswith("arca_")],
      f"남은 행: {[r['id'] for r in _rows if r['id'].startswith('arca_')]}")
check("왜 빠졌는지는 notes 에 남는다",
      any("목록에서 제외" in n for n in _notes),
      f"notes={_notes}")

# ── 사고 3: 활동 0 인 곳이 0 을 달고 목록에 남았다 ───────────────────────────
# 공지·광고만 있는 채널( /b/chatgpt 가 실제로 그랬다 )은 마지막 글 시각이 없다.
_rows, _notes = _com_run(
    arca=lambda path, now=None: (0, "공지를 뺀 글이 사실상 없음", None),
    discourse=lambda api: (0, "최근 7일 글 0건", _com_now - timedelta(days=30)))
check("활동이 0 인 커뮤니티는 0 을 달고 남지 않는다",
      not [r for r in _rows if r["signal_value"] == 0],
      f"0 인 행: {[r['name'] for r in _rows if r['signal_value'] == 0]}")

# ── 사고 4: 옛 캐시가 새 라벨을 달고 살아난다 ────────────────────────────────
# 재는 대상을 바꿔도 하루짜리 캐시가 남아 있으면, 어제 저장한 누적 회원수가
# 오늘 '지금 접속' 이라는 이름표를 달고 그대로 화면에 나온다.
_today = community_mod.date.today().isoformat()
check("버전 없는 옛 캐시는 신선하지 않다고 본다",
      community_mod._cache_fresh(dict(value=18_570_000, checked_at=_today)) is False)
check("버전이 다른 캐시도 신선하지 않다고 본다",
      community_mod._cache_fresh(
          dict(v=community_mod.CACHE_VERSION - 1, value=1, checked_at=_today)) is False)
check("같은 버전의 오늘자 캐시는 쓴다",
      community_mod._cache_fresh(
          dict(v=community_mod.CACHE_VERSION, value=1, checked_at=_today)) is True)

# ── 사고 5: Threads 가 목록에서 사라졌다 ─────────────────────────────────────
# 사용자가 "Threads 는 어디 있나"라고 직접 물은 자리다. 숫자가 없다는 이유로
# 잘리면 안 된다 — want 상한은 숫자가 있는 행에만 걸린다.
_rows, _notes = _com_run(want=1,
                         discord=lambda code, budget, notes: (100, 1000, "ok", None))
_threads = [r for r in _rows if r["name"] == "Threads"]
check("want=1 로 줄여도 '측정 불가' 행(Threads)은 남는다",
      len(_threads) == 1 and _threads[0]["signal_value"] is None,
      f"threads={_threads}")
check("측정 불가 행에는 숫자가 붙지 않는다",
      all(r["signal_value"] is None
          for r in _rows if r["signal_kind"] == "측정 불가"))
check("Threads 사유는 '왜 못 재는지'를 구체적으로 적는다",
      _threads and "keyword_search" in (_threads[0]["note"] or ""),
      f"note={_threads[0]['note'] if _threads else None}")

# ── 카드 계약: web/index.html 이 읽는 키가 전부 있다 ──────────────────────────
check("모든 행이 region/signal_kind/signal_value/mentions/note 를 갖는다",
      all({"id", "name", "url", "domain", "region", "signal_kind",
           "signal_value", "mentions", "note"} <= set(r) for r in _rows))
check("region 은 global/kr 둘 중 하나다",
      all(r["region"] in ("global", "kr") for r in _rows),
      f"{sorted({r['region'] for r in _rows})}")
check("signal_value 는 정수이거나 None 이다 (index.html 이 typeof number 로 본다)",
      all(r["signal_value"] is None or isinstance(r["signal_value"], int)
          for r in _rows))


# ── 아카라이브 파싱: 공지·광고를 활동으로 세지 않는다 ─────────────────────────
# 사고: 목록 HTML 에는 공지·광고 줄도 같은 vrow 로 들어 있다. 그것까지 세면
# 글이 한 건도 없는 채널(/b/chatgpt)이 "글 3건 있는 채널"로 보인다.
def _arca_row(cls, when, comments=0):
    return (f'<a class="vrow column{cls}" href="/b/x/1?p=1">'
            f'<time datetime="{when}"></time>'
            f'<span class="comment-count">[{comments}]</span></a>')


_arca_html = "".join([
    _arca_row(" notice notice-service", "2020-08-18T12:17:31.000Z"),   # 공지
    _arca_row(" notice", "2026-09-21T11:00:00.000Z"),                  # 광고
    _arca_row("", "2026-09-21T12:00:00.000Z", 3),
    _arca_row("", "2026-09-21T11:45:00.000Z", 1),
    _arca_row("", "2026-09-21T11:30:00.000Z", 0),
    _arca_row("", "2026-09-21T11:15:00.000Z", 2),
    _arca_row("", "2026-09-21T11:00:00.000Z", 0),
])
_parsed = community_mod._arca_rows(_arca_html)
check("공지·광고 줄은 활동으로 세지 않는다",
      len(_parsed) == 5, f"{len(_parsed)}건 — 공지/광고가 섞였다")
check("댓글 수를 같이 뽑는다", sum(c for _, c in _parsed) == 6,
      f"{sum(c for _, c in _parsed)}")


class _FakeResp:
    def __init__(self, body):
        self._body = body.encode("utf-8") if isinstance(body, str) else body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# 글 5건이 1시간에 걸쳐 쌓였다 → 간격은 4개 → 하루 96건.
community_mod.urllib.request.urlopen = lambda req, timeout=None: _FakeResp(_arca_html)
try:
    _per_day, _note, _last = community_mod._fetch_arca("/b/x")
finally:
    community_mod.urllib.request.urlopen = _com_orig["urlopen"]
check("아카라이브 하루 글 수는 목록이 쌓인 시간으로 환산한다",
      _per_day == 96, f"{_per_day} (기대 96)")
check("환산이 아니라 원본 측정이 note 에 남는다",
      "5건" in (_note or "") and "댓글" in (_note or ""), f"note={_note}")

# Discourse: 최근 7일 글이 0 이면 마지막 활동을 '죽은 것'으로 돌려준다.
_about = _json.dumps({"about": {"stats": {"posts_7_days": 0, "topics_7_days": 0,
                                          "active_users_7_days": 0}}})
community_mod.urllib.request.urlopen = lambda req, timeout=None: _FakeResp(_about)
try:
    _v, _n, _l = community_mod._fetch_discourse("https://example.invalid/about.json")
finally:
    community_mod.urllib.request.urlopen = _com_orig["urlopen"]
check("최근 7일 글이 0 인 포럼은 죽은 것으로 판정된다",
      _v == 0 and _l is not None
      and (datetime.now(timezone.utc) - _l)
      > timedelta(days=community_mod.DEAD_AFTER_DAYS),
      f"value={_v} last={_l}")

community_mod.time.sleep = _com_orig["sleep"]

# ── 하드 제약: 디시인사이드 수집 코드는 존재하지 않는다 ───────────────────────
# 디시인사이드 이용약관은 비상업·개인 목적을 포함해 자동 수집을 전면 금지한다.
# 목록에 '측정 불가'로 이름만 올리는 것은 되지만, 가져오는 코드가 생기면 안 된다.
# 나중에 누군가 "한 번만" 붙이려 들면 여기서 막힌다.
_fetchers = "\n".join(
    inspect.getsource(fn) for name, fn in vars(community_mod).items()
    if name.startswith("_fetch") and callable(fn))
check("어떤 _fetch_* 함수도 디시인사이드를 건드리지 않는다",
      "dcinside" not in _fetchers.lower(),
      "디시인사이드 수집 코드가 생겼다 — 약관 위반이다")
check("디시인사이드 항목은 전부 kind='unmeasured' 다",
      all(c["kind"] == "unmeasured" for c in community_mod.COMMUNITIES
          if any("dcinside" in m[0] for m in c["match"])))
check("레딧 항목도 전부 kind='unmeasured' 다 (OAuth 앱이 생기기 전까지)",
      all(c["kind"] == "unmeasured" for c in community_mod.COMMUNITIES
          if any("reddit" in m[0] for m in c["match"])))

# ── 국내가 한 사이트로 도배되지 않는다 ───────────────────────────────────────
# 사고: 국내 9행 중 5행이 아카라이브 채널이었다. 사용자가 "아카라이브로
# 도배되어있는데 이상해"라고 반려한 지점이다. 국내에 측정 가능한 곳이 하나라도
# 아카라이브 밖에 있어야 한다.
_kr_measurable = [c for c in community_mod.COMMUNITIES
                  if c["region"] == "kr" and c["kind"] != "unmeasured"]
check("국내 측정 대상에 아카라이브가 아닌 곳이 있다",
      any(c["kind"] != "arca" for c in _kr_measurable),
      f"{[c['id'] for c in _kr_measurable]}")


# ── 유명 MCP 서버가 수집에서 통째로 빠지던 사고 (이슈 34) ───────────────────
# 사용자 지적: "mcp서버 차트에 playwright가 없는 게 이상한데 뭔가?"
# 원인은 필터가 아니라 **수집**이었다. microsoft/playwright-mcp 의 토픽은
# ['mcp', 'playwright'] 뿐인데, 검색 토픽에서 `mcp` 를 뺀 탓에(7.8만 개짜리
# 마케팅 태그라 쓰레기가 올라와서) 우리 눈에 아예 안 들어왔다.
# 아래 셋은 그 사고가 되살아나면 각각 다른 자리에서 잡는다.

_PLAYWRIGHT_MCP = {
    "full_name": "microsoft/playwright-mcp",
    "name": "playwright-mcp",
    "description": "Playwright MCP server",
    "topics": ["mcp", "playwright"],
    "stargazers_count": 37390,
    "html_url": "https://github.com/microsoft/playwright-mcp",
    "pushed_at": "2026-09-20T00:00:00Z",
    "archived": False,
    "fork": False,
}

check("이름·설명으로 MCP 서버를 찾는 질의가 있다",
      bool(getattr(gh_mod, "NAME_DESC_SEARCHES", None)),
      "토픽만 쓰면 playwright-mcp 처럼 topic:mcp 만 단 레포가 통째로 빠진다")

if getattr(gh_mod, "NAME_DESC_SEARCHES", None):
    _queries = [q for q, _ in gh_mod.NAME_DESC_SEARCHES]
    check("질의가 설명과 이름 양쪽을 본다",
          any("in:description" in q for q in _queries)
          and any("in:name" in q for q in _queries),
          f"{_queries}")
    # topic:mcp 를 되살리면 open-webui·netdata·JeecgBoot 가 MCP 서버가 된다.
    # 실측으로 확인한 사실이라, 되돌리려는 시도를 여기서 막는다.
    check("검색 토픽에 마케팅 태그 `mcp` 를 되살리지 않았다",
          "mcp" not in gh_mod.KINDS["MCP 서버"],
          "topic:mcp 상위 30건에 웹 UI·모니터링·로우코드 플랫폼이 섞인다")

check("playwright-mcp 는 우리 필터를 통과한다",
      gh_mod._usable(_PLAYWRIGHT_MCP)[0],
      "걸러지는 게 아니라 수집되지 않는 것이 원인이었다")

check("playwright-mcp 를 MCP 서버로 판정한다",
      gh_mod._detect_kind(_PLAYWRIGHT_MCP, "스킬") == "MCP 서버",
      f'판정={gh_mod._detect_kind(_PLAYWRIGHT_MCP, "스킬")} — '
      "설명에 'MCP server' 라고 적혀 있는데 다른 종류로 갔다")

check("playwright-mcp 를 브라우저 자동화로 분류한다",
      gh_mod._classify(_PLAYWRIGHT_MCP) == "브라우저 자동화",
      f"분류={gh_mod._classify(_PLAYWRIGHT_MCP)}")

# 수집 경로 자체를 확인한다 — 네트워크 없이, 가짜 응답으로.
_named_pool, _named_seen, _named_buckets = [], set(), {}
_named_calls = []


class _FakeBudget:
    def check(self, key):
        pass

    def spend(self, key):
        pass


class _NoWaitPacer:
    def wait(self):
        _named_calls.append("wait")

    def cooldown(self):
        pass


_orig_get = gh_mod._get
try:
    gh_mod._get = lambda url, token=None: (
        _named_calls.append(url) or {"items": [_PLAYWRIGHT_MCP]}
    )
    _spent = gh_mod._search_named(None, _FakeBudget(), [], _NoWaitPacer(),
                                  _named_pool, _named_seen, _named_buckets)
finally:
    gh_mod._get = _orig_get

check("이름·설명 검색이 playwright-mcp 를 풀에 넣는다",
      any(r.get("full_name") == "microsoft/playwright-mcp" for r in _named_pool),
      f"풀 {len(_named_pool)}건")
check("그 결과가 (MCP 서버, 브라우저 자동화) 칸에 들어간다",
      ("MCP 서버", "브라우저 자동화") in _named_buckets,
      f"칸 {list(_named_buckets)}")
check("이름·설명 검색도 레이트리밋 페이서를 거친다",
      _named_calls.count("wait") == len(gh_mod.NAME_DESC_SEARCHES),
      "페이서를 건너뛰면 403 을 먹고 질의가 통째로 사라진다")



# 토픽이 아예 없는 대형 레포가 통째로 빠지던 사고 (이슈 34, 2차).
# 사용자 지적: "다른 카테고리도 점검같이해줘 / 비슷한 논리로 누락되었을 가능성".
# 실측 결과 MCP 만의 문제가 아니었다 — CLI·개발도구 상위 19개 중 6개,
# 에이전트 프레임워크 상위 20개 중 12개가 보드에 없었고, 셋 다 topics=[] 였다.
check("네 종류 모두 이름·설명 질의를 갖는다",
      {k for _, k in gh_mod.NAME_DESC_SEARCHES} == set(gh_mod.KINDS),
      f"{sorted({k for _, k in gh_mod.NAME_DESC_SEARCHES})} — "
      "토픽 없는 대형 레포는 이 그물로만 잡힌다")

# 토픽이 비어 있어도 종류가 올바로 정해져야 한다. 안 그러면 질의로 데려와도
# 엉뚱한 칸에 들어간다.
_NO_TOPIC_CASES = [
    ({"full_name": "cline/cline", "name": "cline",
      "description": "Autonomous coding agent right in your IDE",
      "topics": [], "stargazers_count": 68872}, "CLI·개발도구", "CLI·개발도구"),
    ({"full_name": "openai/swarm", "name": "swarm",
      "description": "Educational framework exploring ergonomic, lightweight "
                     "multi-agent orchestration.",
      "topics": [], "stargazers_count": 21996},
     "에이전트 프레임워크", "에이전트 프레임워크"),
]
for _repo, _fallback, _want in _NO_TOPIC_CASES:
    _got = gh_mod._detect_kind(_repo, _fallback)
    check(f"토픽이 없는 {_repo['name']} 을 {_want} 로 본다", _got == _want, f"판정={_got}")

print(f"\n{len(PASS)} 통과 / {len(FAIL)} 실패")
if FAIL:
    print("실패:", ", ".join(FAIL))
raise SystemExit(1 if FAIL else 0)
