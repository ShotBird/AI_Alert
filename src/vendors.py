"""모델 업데이트 — 벤더별 현황판.

뉴스 피드가 아니다. "지금 각 회사의 최신 모델이 무엇이고 마지막 갱신이 언제였나"를
한 줄씩 보여주는 **상태판**이다. 같은 소식이 흘러가는 뉴스 섹션과 역할이 다르다.

**'계획'은 넣지 않는다.** 벤더는 출시 일정을 공표하지 않는다. 떠도는 소문을 일정처럼
적으면 그건 정보가 아니라 오보다. 대신 "마지막 갱신 이후 며칠"을 보여준다 —
오래 조용한 회사가 곧 뭔가 낼 가능성이 높다는 것은 사용자가 직접 읽어낼 몫이다.

출처가 벤더마다 다르다는 사실도 숨기지 않는다. 티켓 09 에서 확인한 대로
가중치를 공개하는 회사는 Hugging Face 로 당일 잡히지만, Anthropic·OpenAI·xAI 는
클로즈드라 발표문이나 뉴스로만 알 수 있다.
"""

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone

HF_API = "https://huggingface.co/api/models"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")

# 현황판에 고정으로 올리는 회사들. 소식이 없어도 줄은 남는다 —
# "이 회사는 조용하다"도 정보이기 때문이다.
VENDORS = [
    dict(id="anthropic", name="Anthropic", hf=None,
         terms=["claude", "앤트로픽", "anthropic", "sonnet", "opus", "haiku"]),
    dict(id="openai", name="OpenAI", hf=None,
         terms=["gpt", "오픈ai", "openai", "chatgpt", "o3", "o4"]),
    dict(id="google", name="Google", hf="google",
         terms=["gemini", "제미나이", "gemma"]),
    dict(id="meta", name="Meta", hf="meta-llama",
         terms=["llama", "라마"]),
    dict(id="xai", name="xAI", hf=None,
         terms=["grok", "그록"]),
    dict(id="deepseek", name="DeepSeek", hf="deepseek-ai",
         terms=["deepseek", "딥시크"]),
    dict(id="qwen", name="Alibaba Qwen", hf="Qwen",
         terms=["qwen", "큐원"]),
    dict(id="moonshot", name="Moonshot", hf="moonshotai",
         terms=["kimi", "moonshot", "문샷", "키미"]),
    dict(id="mistral", name="Mistral", hf="mistralai",
         terms=["mistral", "미스트랄", "magistral", "devstral"]),
    dict(id="zai", name="Z.ai (GLM)", hf="zai-org",
         terms=["glm", "zhipu", "z.ai"]),
    dict(id="upstage", name="Upstage", hf="upstage",
         terms=["solar", "업스테이지", "upstage"]),
]


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _hf_latest(author):
    """이 회사가 Hugging Face 에 마지막으로 올린 모델."""
    url = (f"{HF_API}?author={author}&sort=createdAt&direction=-1&limit=5")
    try:
        data = _get(url)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError):
        return None
    for m in data or []:
        rid = m.get("id") or ""
        created = m.get("createdAt")
        if not rid or not created:
            continue
        try:
            when = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except ValueError:
            continue
        return dict(name=rid.split("/", 1)[-1], url=f"https://huggingface.co/{rid}",
                    at=when, via="Hugging Face")
    return None


def _mentions_many(title):
    """제목에 회사가 둘 이상 나오는가.

    "오픈AI, 기업 시장 점유율 역전…앤트로픽, IPO전 신형 모델 출시 검토" 같은 기사가
    Anthropic 과 OpenAI 양쪽의 '최신 모델'로 동시에 올라간 일이 있었다.
    이런 건 업계 기사이지 어느 한 회사의 출시가 아니다.
    """
    low = title.lower()
    hit = 0
    for v in VENDORS:
        if any(t in low for t in v["terms"]):
            hit += 1
            if hit > 1:
                return True
    return False


def _from_items(vendor, items):
    """수집한 항목 중 이 회사의 출시로 보이는 가장 최근 것."""
    best = None
    for item in items:
        if not item.get("is_release"):
            continue
        low = item["title"].lower()
        if not any(t in low for t in vendor["terms"]):
            continue
        # 업계 기사는 현황판에 올리지 않는다
        if _mentions_many(item["title"]):
            continue
        # "검토", "전망", "예상"은 출시가 아니다. 현황판은 일어난 일만 싣는다.
        if any(w in low for w in ("검토", "전망", "예상", "소문", "루머",
                                  "rumor", "reportedly", "could ", "may ")):
            continue
        when = item.get("published_at")
        if when is None:
            continue
        if best is None or when > best["at"]:
            best = dict(name=item["title"], url=item["url"], at=when,
                        via=item["source_name"])
    return best


def vendor_status(items, now=None):
    """벤더별 현황 행과 notes."""
    now = now or datetime.now(timezone.utc)
    rows, notes, hf_failures = [], [], 0

    for vendor in VENDORS:
        hit = None
        if vendor["hf"]:
            hit = _hf_latest(vendor["hf"])
            if hit is None:
                hf_failures += 1

        # 뉴스·발표문 쪽이 더 최신이면 그쪽을 쓴다. 클로즈드 벤더는 이쪽뿐이다.
        from_news = _from_items(vendor, items)
        if from_news and (hit is None or from_news["at"] > hit["at"]):
            hit = from_news

        if hit is None:
            rows.append(dict(vendor=vendor["name"], model=None, url=None,
                             days=None, via=None, weights=bool(vendor["hf"])))
            continue

        days = max(0, int((now - hit["at"]).total_seconds() // 86400))
        rows.append(dict(vendor=vendor["name"], model=hit["name"], url=hit["url"],
                         days=days, via=hit["via"], weights=bool(vendor["hf"])))

    # 최근에 움직인 회사를 위로. 소식이 없는 회사는 맨 아래에 남긴다.
    rows.sort(key=lambda r: (r["days"] is None, r["days"] if r["days"] is not None else 0))

    if hf_failures:
        notes.append(f"Hugging Face 조회 {hf_failures}건 실패 — "
                     "해당 회사는 발표문·뉴스 기준으로만 표시됩니다.")
    notes.append("모델 업데이트는 '현황'이지 '계획'이 아닙니다. "
                 "벤더가 출시 일정을 공표하지 않으므로 마지막 갱신 이후 경과일만 보여줍니다.")
    return rows, notes
