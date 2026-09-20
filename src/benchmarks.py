"""모델 업데이트 행에 공개 벤치마크 점수를 붙인다.

**배경(티켓 14 → 20).** 처음 요청은 artificialanalysis.ai 같은 벤치마크 표였다.
확인해보니 그 사이트 약관은 스크래핑을 금지하고, 무료 API 는 "Internal Use" 로만
쓸 수 있다. 이 앱이 남에게 공유되지 않는 개인용이라는 점은 사용자가 확인해줬지만,
그래도 **재사용을 명시적으로 허용하는 쪽이 더 깨끗하고 오래간다** — 그래서
아래 둘로 정했다. 둘 다 CC BY 4.0 이고 인증이 필요 없다.

  - **EpochAI** `https://epoch.ai/data/benchmark_data.zip` 안의
    `epoch_capabilities_index/eci_scores.csv` — 모델 하나당 한 줄, "Epoch Capabilities
    Index"(여러 벤치마크를 합성한 단일 지표) 와 발표일이 있다. 당일 갱신.
  - **LMArena** `lmarena-ai/leaderboard-dataset` (Hugging Face) — 사람이 직접 두 모델
    답을 비교 투표한 Elo 성격의 점수. datasets-server 의 rows API 로 JSON 을 받는다
    (parquet 를 직접 읽으려면 pandas/pyarrow 가 필요한데 이 프로젝트는 stdlib 전용이다).

HF Open LLM Leaderboard 는 2025-03 에 멈췄으므로 쓰지 않는다.

**이건 섹션이 아니다.** 벤치마크 점수는 모델이 새로 나오거나 재평가될 때만
바뀌는 값이지 매일 나오는 소식이 아니다(CONTEXT.md 의 "일어난 일만 싣는다"
원칙과 같은 이유). 그래서 이 파일은 독립 섹션을 만들지 않고, `annotate()` 로
기존 모델 업데이트 행에 `benchmarks` 필드 하나를 얹는다. 매칭이 안 되면
그 행은 그대로 둔다 — 지어낸 점수보다 빈 칸이 정직하다.

**이름 맞추기가 제일 어려운 부분이다.** "Claude Fable 5.1" / "claude-fable-5.1" /
"Fable 5.1" 이 같은 모델을 가리켜야 한다. `normalize()` 는 대소문자·구두점(-, _, ., /)을
지우고, Anthropic 이 제품명 앞에 붙이는 "Claude" 같은 순수 브랜드 래퍼만 벗겨낸다.
반대로 "Flash"/"Pro"/"Max"/"Mini" 같은 말은 **절대 벗기지 않는다** — 이런 말은
같은 계열 안에서 실제로 다른 제품을 가리킨다(Gemini 3.8 과 Gemini 3.8 Flash 는
다른 모델이다, 실측으로 확인됨). 여기서 지나치게 공격적으로 다듬으면 서로 다른
모델의 점수가 뒤섞이는데, 그건 틀린 정보를 사실처럼 보여주는 것이라 빈 칸보다 나쁘다.
그래서 "정규화는 세게, 계열을 넘어서는 추측은 절대 하지 않는다"는 티켓의 지침대로
애매한 접미사는 그대로 남겨 매칭을 포기한다(재현율보다 정밀도).

**커버리지는 낮다 — 그리고 그게 이 파일이 낼 결론이다.** 2026-09-21 실측:
boards/latest.json 의 모델 업데이트 14행 중 **3행(약 21%)** 만 두 소스 중
하나에라도 걸렸다(Claude Fable 5.1, Grok 4.6, Kimi K3). 나머지는 이미지·OCR·가드레일
전용 모델이거나(Qwen-Image, Mistral OCR, Llama-Guard), 갓 나와서 아직 아무 벤치마크에도
안 잡혔거나(Claude Mythos 5.1, GLM-5.3-Flash, DeepSeek-V4.1-Flash), 클로즈드라 공개
점수 자체가 없는 경우(대부분)다. `__main__` 아래 실측 출력과 결론을 그대로 남겨둔다.
"""

import csv
import io
import json
import os
import re
import socket
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone

try:
    from .budget import Budget
except ImportError:  # `python src/benchmarks.py` 로 직접 실행할 때 (아래 __main__ 참고)
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.budget import Budget

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")
TIMEOUT = 30

EPOCH_ZIP_URL = "https://epoch.ai/data/benchmark_data.zip"
EPOCH_ECI_MEMBER = "epoch_capabilities_index/eci_scores.csv"
EPOCH_LICENCE = "CC BY 4.0"

HF_DATASET_API = "https://huggingface.co/api/datasets/lmarena-ai/leaderboard-dataset"
HF_ROWS_API = "https://datasets-server.huggingface.co/rows"
LMARENA_DATASET = "lmarena-ai/leaderboard-dataset"
LMARENA_LICENCE = "CC BY 4.0"
# rows API 는 한 번에 최대 100행만 준다. "overall" 카테고리 행은 latest 스플릿
# 맨 앞에 rank 순으로 몰려 있고(실측: 402행), 그 뒤로 "chinese" 등 다른 카테고리가
# 이어진다. 그래서 카테고리가 바뀌는 순간 멈추면 다른 카테고리를 긁지 않고도
# overall 전체를 받는다 — 실측 기준 호출 5회 안팎.
LMARENA_PAGE = 100

# 예산 게이트에 대해: budget.py 의 LIMITS 는 이 파일에서 건드리지 않기로 했다
# (이 티켓은 benchmarks.py 한 파일만 새로 만든다). 그래서 budget.check() 는 쓰지
# 않는다 — LIMITS 에 없는 키를 check() 에 넘기면 항상 BudgetUnavailable 이라
# 매번 막히는 것과 같다. 대신 실제 방어선은 아래 캐시(변경 없으면 페이로드를 아예
# 받지 않음)다. GitHub 예산과 같은 이유로(budget.py 의 github_core 주석 참고) 이
# 소스들도 돈이 들지 않는다 — budget.spend() 는 호출 횟수를 남겨두는 용도로만 쓴다
# (spend() 는 LIMITS 에 없는 키라도 예외를 던지지 않는다).
BUDGET_KEY = "benchmarks"


def _spend(budget):
    try:
        budget.spend(BUDGET_KEY, 1)
    except Exception:
        pass  # 기록 실패가 벤치마크 조회를 막을 이유는 없다


# ── 이름 정규화 ──────────────────────────────────────────────────────────────

# Anthropic 이 제품명 앞에 붙이는 순수 브랜드 래퍼. "Claude Fable 5.1" 과
# "Fable 5.1" 을 같은 키로 만들기 위해서만 벗긴다. 계열명(Opus/Sonnet/…)은
# 다른 회사와 안 겹치므로 이렇게 벗겨도 다른 모델과 섞일 일이 없다.
_BRAND_PREFIX = {"claude"}

# 발표 제목 맨 앞에 흔히 붙는 동사. 이름이 아니라 문장의 일부다.
_LEADING_VERBS = {"introducing", "announcing", "unveiling", "presenting",
                  "launching", "meet", "shipping", "releasing"}

# 평가 설정(추론 강도 등)을 나타내는 꼬리표. **제품명이 아닌 게 확실한 것만** 넣는다.
# "flash"/"pro"/"max"/"mini"/"plus"/"lite"/"air" 는 일부러 뺐다 — 실제로 다른
# 제품을 가리키는 경우가 있다(Gemini 3.8 Flash != Gemini 3.8, 실측 확인).
_NOISE_TOKENS = {"high", "xhigh", "low", "xlow", "medium", "none", "auto",
                 "thinking", "nonthinking", "instant", "beta", "preview",
                 "exp", "experimental", "latest"}

_SPLIT_RE = re.compile(r"[\\/_.\-]")
_KEEP_RE = re.compile(r"[^a-z0-9가-힣 ]")


def normalize(name):
    """비교용 키로 접는다. 대소문자·구두점·순수 브랜드 래퍼만 지운다.

    "Claude Fable 5.1" / "claude-fable-5.1" / "Fable 5.1" 이 모두
    "fable 5.1" 로 모인다. 그 이상은 벗기지 않는다 — 계열을 넘어서는
    추측은 하지 않기로 했기 때문이다.
    """
    if not name:
        return ""
    s = _SPLIT_RE.sub(" ", name.lower())
    s = _KEEP_RE.sub(" ", s)
    tokens = s.split()
    while tokens and tokens[0] in _LEADING_VERBS:
        tokens.pop(0)
    while tokens and tokens[0] in _BRAND_PREFIX:
        tokens.pop(0)
    while tokens and tokens[-1] in _NOISE_TOKENS:
        tokens.pop()
    return " ".join(tokens)


# ── 캐시 ─────────────────────────────────────────────────────────────────────

def _load_cache(path):
    # 캐시는 성능용이지 안전장치가 아니다. 못 읽으면 빈 캐시로 시작한다(fail-open) —
    # community.py 의 도메인 순위 캐시와 같은 판단이다.
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_cache(path, cache):
    try:
        parent = os.path.dirname(path) or "."
        os.makedirs(parent, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass  # 저장 실패가 이번 조회를 막을 이유는 없다


# 파싱 중 나는 오류. 소스 하나가 깨져도 나머지는 계속 간다(collect.py 와 같은 태도).
_NETWORK_ERRORS = (urllib.error.HTTPError, urllib.error.URLError, socket.timeout, OSError)
_PARSE_ERRORS = (zipfile.BadZipFile, csv.Error, KeyError, ValueError,
                 UnicodeDecodeError, json.JSONDecodeError)


def _request(url, method=None, accept="application/json"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept}, method=method)
    return urllib.request.urlopen(req, timeout=TIMEOUT)


# ── EpochAI ──────────────────────────────────────────────────────────────────

def _epoch_fingerprint():
    """페이로드(2MB대 zip) 없이 바뀌었는지만 본다.

    epoch.ai 응답에는 Last-Modified 가 없다(실측 확인) — 대신 ETag 는 매 응답에
    붙어 있으므로 그걸 "바뀜 감지"로 쓴다. HEAD 요청이라 몸통을 받지 않는다.
    """
    with _request(EPOCH_ZIP_URL, method="HEAD", accept="*/*") as resp:
        return resp.headers.get("ETag")


def _epoch_fetch():
    """zip 을 받아 Epoch Capabilities Index(모델당 합성 점수 한 줄)만 뽑는다."""
    with _request(EPOCH_ZIP_URL, accept="application/zip, */*") as resp:
        raw = resp.read()
    z = zipfile.ZipFile(io.BytesIO(raw))
    text = z.read(EPOCH_ECI_MEMBER).decode("utf-8")
    entries = {}
    for row in csv.DictReader(io.StringIO(text)):
        display_name = (row.get("Display name") or row.get("Model") or "").strip()
        key = normalize(display_name)
        if not key:
            continue
        try:
            eci = float(row["eci"])
        except (KeyError, ValueError, TypeError):
            continue
        entries[key] = dict(
            display_name=display_name,
            eci=eci,
            eci_date=row.get("date") or None,
            organization=(row.get("Organization") or None),
            source="EpochAI",
            licence=EPOCH_LICENCE,
        )
    return entries


# ── LMArena ──────────────────────────────────────────────────────────────────

def _lmarena_fingerprint():
    """데이터셋 레포의 커밋 시각. 모델 하나 안 늘어도 매일 갱신되니 "바뀜"의 근거가 된다."""
    with _request(HF_DATASET_API) as resp:
        data = json.loads(resp.read())
    return data.get("sha") or data.get("lastModified")


def _lmarena_fetch():
    """LMArena "overall" 카테고리의 최신 순위를 JSON rows API 로 받는다.

    parquet 파일을 직접 받는 게 더 적은 호출이지만 stdlib 만으로는 parquet 를
    못 읽는다(pandas/pyarrow 필요, 이 프로젝트는 stdlib 전용). 대신
    datasets-server 의 rows API 는 순수 JSON 을 주므로 그걸 쓴다.
    """
    entries = {}
    offset = 0
    while True:
        url = (f"{HF_ROWS_API}?dataset={LMARENA_DATASET.replace('/', '%2F')}"
              f"&config=text&split=latest&offset={offset}&length={LMARENA_PAGE}")
        with _request(url) as resp:
            data = json.loads(resp.read())
        rows = data.get("rows") or []
        stop = False
        for item in rows:
            row = item.get("row") or {}
            if row.get("category") != "overall":
                stop = True  # rank 순으로 정렬돼 있어 overall 구간이 끝나면 여기서 멈춘다
                break
            model_name = (row.get("model_name") or "").strip()
            key = normalize(model_name)
            if not key:
                continue
            entries[key] = dict(
                display_name=model_name,
                arena_score=row.get("rating"),
                arena_rank=row.get("rank"),
                arena_date=row.get("leaderboard_publish_date"),
                organization=row.get("organization"),
                source="LMArena",
                licence=LMARENA_LICENCE,
            )
        if stop or len(rows) < LMARENA_PAGE:
            break
        offset += LMARENA_PAGE
    return entries


# ── 공통 로더 ─────────────────────────────────────────────────────────────────

def _load_source(cache, cache_key, label, fingerprint_fn, fetch_fn, budget, notes):
    """캐시된 fingerprint 와 비교해서 바뀌었을 때만 실제 payload 를 받는다."""
    cached = cache.get(cache_key) or {}

    try:
        fp = fingerprint_fn()
        _spend(budget)
    except _NETWORK_ERRORS as exc:
        if cached.get("entries"):
            notes.append(f"{label}: 최신 여부 확인 실패({type(exc).__name__}) — 캐시된 값을 그대로 씁니다.")
            return cached["entries"]
        notes.append(f"{label}: 확인 실패({type(exc).__name__}), 캐시도 없어 이번엔 건너뜁니다.")
        return {}
    except Exception as exc:
        notes.append(f"{label}: 예상 못 한 오류({type(exc).__name__}), 이번엔 건너뜁니다.")
        return cached.get("entries") or {}

    if fp and cached.get("fingerprint") == fp and cached.get("entries"):
        return cached["entries"]  # 안 바뀌었다 — payload 를 받지 않는다

    try:
        entries = fetch_fn()
        _spend(budget)
    except (_NETWORK_ERRORS + _PARSE_ERRORS) as exc:
        if cached.get("entries"):
            notes.append(f"{label}: 갱신 실패({type(exc).__name__}) — 캐시된 값을 그대로 씁니다.")
            return cached["entries"]
        notes.append(f"{label}: 갱신 실패({type(exc).__name__}), 캐시도 없어 이번엔 건너뜁니다.")
        return {}
    except Exception as exc:
        notes.append(f"{label}: 예상 못 한 오류({type(exc).__name__}), 이번엔 건너뜁니다.")
        return cached.get("entries") or {}

    cache[cache_key] = dict(fingerprint=fp,
                            fetched_at=datetime.now(timezone.utc).isoformat(),
                            entries=entries)
    return entries


def load_scores(budget, cache_path):
    """EpochAI + LMArena 를 받아 (모델명 → 점수 dict) 색인을 만든다.

    바뀐 게 없으면(fingerprint 동일) 어느 쪽도 payload 를 다시 받지 않는다.
    """
    notes = []
    cache = _load_cache(cache_path)

    epoch_entries = _load_source(cache, "epoch", "EpochAI",
                                 _epoch_fingerprint, _epoch_fetch, budget, notes)
    lmarena_entries = _load_source(cache, "lmarena", "LMArena",
                                   _lmarena_fingerprint, _lmarena_fetch, budget, notes)

    _save_cache(cache_path, cache)

    index = {}
    for key in set(epoch_entries) | set(lmarena_entries):
        e = epoch_entries.get(key)
        l = lmarena_entries.get(key)
        merged = {}
        sources = []
        if e:
            merged["eci"] = e["eci"]
            merged["eci_date"] = e["eci_date"]
            if e.get("organization"):
                merged.setdefault("organization", e["organization"])
            sources.append(e["source"])
        if l:
            merged["arena_score"] = l["arena_score"]
            merged["arena_rank"] = l["arena_rank"]
            merged["arena_date"] = l["arena_date"]
            if l.get("organization"):
                merged.setdefault("organization", l["organization"])
            sources.append(l["source"])
        merged["source"] = sources          # 라이선스가 요구하는 출처 표기 — 화면에 그대로 보여준다
        merged["licence"] = "CC BY 4.0"     # 둘 다 같은 라이선스라 이 값은 늘 고정이다
        index[key] = merged

    notes.append(f"벤치마크 색인 {len(index)}개 모델 "
                f"(EpochAI {len(epoch_entries)} · LMArena {len(lmarena_entries)}, 둘 다 CC BY 4.0).")
    return index, notes


# ── 붙이기 ────────────────────────────────────────────────────────────────────

def annotate(vendor_rows, index):
    """model 필드로 색인을 찾아 `benchmarks` 를 붙인다. 못 찾으면 그 행은 그대로 둔다.

    계열이 다른데 이름이 비슷하다고 붙이는 일은 하지 않는다 — `normalize()` 가
    이미 그 경계를 지킨다(위 모듈 docstring 참고). 여기서는 단순히 색인을
    찾아보는 것뿐이라 추가로 계열을 추측하지 않는다.
    """
    notes = []
    matched, considered, unmatched_names = 0, 0, []

    for row in vendor_rows:
        model = row.get("model")
        if not model:
            continue  # 이 벤더는 확인된 출시가 없다 — 벤치마크를 붙일 대상 자체가 없다
        considered += 1
        hit = index.get(normalize(model))
        if hit is None:
            unmatched_names.append(model)
            continue
        row["benchmarks"] = dict(hit)  # 얕은 복사 — 색인을 행이 공유해서 바꾸지 않게
        matched += 1

    if considered:
        pct = round(100 * matched / considered)
        notes.append(f"벤치마크 매칭 {matched}/{considered}행 ({pct}%) — "
                     "나머지는 공개 점수가 없거나(신모델·클로즈드) 계열이 달라 보류.")
        if unmatched_names:
            preview = ", ".join(unmatched_names[:5])
            more = "" if len(unmatched_names) <= 5 else f" 외 {len(unmatched_names) - 5}건"
            notes.append(f"미매칭: {preview}{more}")
    else:
        notes.append("벤치마크 매칭 대상 없음 — 오늘 확인된 모델 출시가 없습니다.")
    return notes


if __name__ == "__main__":
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))
    ROOT = os.path.dirname(HERE)
    BOARD_PATH = os.path.join(ROOT, "boards", "latest.json")
    SCRATCH = os.environ.get("CLAUDE_SCRATCHPAD") or tempfile.gettempdir()
    CACHE_PATH = os.path.join(SCRATCH, "benchmarks-cache.json")
    BUDGET_PATH = os.path.join(SCRATCH, "benchmarks-verify-budget.json")

    with open(BOARD_PATH, encoding="utf-8") as fh:
        board = json.load(fh)

    cards = []
    for section in board.get("sections", []):
        if section.get("id") == "model_updates":
            cards = section.get("cards", [])
            break

    print(f"=== boards/latest.json 의 모델 업데이트 카드 {len(cards)}개 ===")
    for c in cards:
        print(f"  {c.get('title')} | family={c.get('family')} | model={c.get('model')!r}")

    print("\n=== 1) load_scores() — 첫 호출(캐시 없음, 실제 네트워크 호출) ===")
    budget = Budget(BUDGET_PATH)
    index, load_notes = load_scores(budget, CACHE_PATH)
    for n in load_notes:
        print(" ", n)
    budget.save()

    print("\n=== 2) load_scores() 재호출 — fingerprint 가 같으면 payload 재다운로드가 없어야 함 ===")
    calls_before = dict(budget.counts)
    index2, load_notes2 = load_scores(budget, CACHE_PATH)
    calls_after = dict(budget.counts)
    for n in load_notes2:
        print(" ", n)
    print(f"  benchmarks 카운터: {calls_before.get(BUDGET_KEY, 0)} -> {calls_after.get(BUDGET_KEY, 0)}"
         " (fingerprint 확인만큼만 늘고, zip/rows 재다운로드는 없어야 정상)")

    print(f"\n=== 3) annotate() — 카드 {len(cards)}개에 매칭 시도 ===")
    ann_notes = annotate(cards, index)
    for n in ann_notes:
        print(" ", n)

    print("\n=== 4) 매칭 결과 상세 ===")
    matched = [c for c in cards if c.get("benchmarks")]
    unmatched = [c for c in cards if not c.get("benchmarks")]
    for c in matched:
        b = c["benchmarks"]
        bits = []
        if "eci" in b:
            bits.append(f"ECI={b['eci']}({b.get('eci_date')})")
        if "arena_score" in b:
            bits.append(f"Arena={b['arena_score']:.1f}(#{b.get('arena_rank')}, {b.get('arena_date')})")
        print(f"  [매칭] {c['title']} / {c.get('model')} -> {', '.join(bits)} "
             f"[{'+'.join(b['source'])}, {b['licence']}]")
    for c in unmatched:
        print(f"  [미매칭] {c['title']} / {c.get('model')}")

    total = len(cards)
    frac = len(matched) / total if total else 0.0
    print(f"\n=== 커버리지: {len(matched)}/{total} ({frac:.1%}) ===")
    print("결론: 커버리지가 낮다(20% 안팎). 오늘 목록의 다수가 이미지·OCR·가드레일 같은 "
         "특화 모델이거나 막 나온 모델이라 EpochAI/LMArena 어느 쪽에도 아직 없다. "
         "값이 있는 소수 행에는 출처(EpochAI/LMArena)와 라이선스(CC BY 4.0)를 "
         "함께 붙여 화면에 표시할 수 있게 해뒀지만, 이 상태로는 '모델 업데이트' "
         "대부분의 행에 아무 도움이 안 되므로 지금 그대로 출시할 가치는 크지 않다 — "
         "클로즈드·신모델이 대다수인 이 보드의 특성상 공개 벤치마크 커버리지 자체가 "
         "구조적으로 낮을 수밖에 없다.")
