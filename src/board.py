"""보드 조립. 티켓 05가 정한 계약 그대로 만든다.

지켜야 할 것 둘:
  - 섹션이 비면 **지우지 않고** 이유와 함께 비워둔다. 사라진 섹션은 버그처럼 보이고,
    이유가 적힌 빈 섹션은 알려진 구멍처럼 보인다.
  - 본문·발췌문은 넣지 않는다. 제목 + 한 줄 요약 + 링크까지만. 그래야 작게 유지된다.
"""

import json
import math
import os

# 레포 → 한국어 한 줄. LLM 키가 없는 동안 쓰는 씨앗 캐시다.
# summarize.py 가 켜지면 summary_ko 가 채워지고 이 값은 자동으로 뒷전이 된다.
_NOTES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "state", "skill-notes.json")


_NEWS_NOTES_PATH = os.path.join(os.path.dirname(_NOTES_PATH), "news-notes.json")


def _load_notes(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _skill_notes():
    return _load_notes(_NOTES_PATH)


def _news_notes():
    """해외 기사의 한국어 한 줄. 키가 없는 동안 쓰는 씨앗 캐시."""
    return _load_notes(_NEWS_NOTES_PATH)
from datetime import datetime, timezone

SCHEMA_VERSION = "1.0"
PER_SECTION = 5
# 뉴스는 지역별로 따로 뽑는다. 한 목록에 섞으면 그날 영어권이 시끄러울 때
# 국내 기사가 한 건도 못 올라온다.
PER_REGION = 4
# 한 매체가 섹션을 통째로 먹지 못하게 한다. 실제로 AI타임스 하나가
# 뉴스 5칸을 다 차지하는 일이 있었다 — 그건 보드가 아니라 그 매체의 목차다.
MAX_PER_SOURCE = 2

SECTION_TITLES = {
    "model_updates": "모델 업데이트",
    "github_skills": "GitHub 급상승",
    "top_headlines": "뉴스",
    "communities": "AI 커뮤니티",
    "keywords": "오늘의 키워드",
}


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if dt else None


def load_previous(boards_dir):
    """어제 보드. 변화(신규/지속) 판정에 쓴다. 없으면 전부 신규가 된다."""
    path = os.path.join(boards_dir, "latest.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _previous_keys(prev):
    if not prev:
        return set()
    keys = set()
    for section in prev.get("sections", []):
        for card in section.get("cards", []):
            k = card.get("dedup_key")
            if k:
                keys.add(k)
    return keys


def _card(cluster, seq, board_date, prev_keys):
    from .cluster import canonical_url, normalize_title
    key = canonical_url(cluster["url"]) or normalize_title(cluster["title"])
    change = "continuing" if key in prev_keys else "new"
    sources = []
    for name in cluster["sources"][:3]:      # 최대 3개. 크기를 묶어두기 위한 것
        entry = {"name": name}
        if cluster.get("engagement"):
            entry["engagement"] = cluster["engagement"]
        sources.append(entry)
    return {
        "id": f"c_{board_date}_{seq:03d}",
        "title": cluster["title"],
        "summary_ko": None,            # LLM 요약은 API 키가 생기면 채운다
        "url": cluster["url"],
        "heat": cluster["heat"],
        "source_count": cluster["source_count"],
        "sources": sources,
        "change": change,
        "dedup_key": key,
        "published_at": _iso(cluster.get("published_at")),
    }


def build(clusters_by_section, github_rows, sources_status, budget_report,
          boards_dir, now=None, notes=None, community_rows=None,
          vendor_rows=None, keyword_rows=None, milestone=None):
    now = now or datetime.now(timezone.utc)
    board_date = now.astimezone().date().isoformat()

    prev = load_previous(boards_dir)
    prev_keys = _previous_keys(prev)

    sections, seq = [], 0
    # 키워드가 맨 앞이다. 화면에서도 헤더 바로 아래 작은 띠로 뜬다.
    for sid in ("keywords", "model_updates", "github_skills", "top_headlines",
                "communities"):
        cards, empty_reason = [], None

        notes_map = _skill_notes() if sid == "github_skills" else {}
        news_notes = _news_notes() if sid == "top_headlines" else {}

        if sid == "model_updates" and vendor_rows is not None:
            # 뉴스가 아니라 현황판이다. 소식이 없는 회사도 줄은 남긴다 —
            # "이 회사는 조용하다"도 정보이기 때문이다.
            for row in vendor_rows:
                seq += 1
                cards.append({
                    "id": f"v_{board_date}_{seq:03d}",
                    "title": row["vendor"],
                    "family": row.get("family"),
                    "headline": row.get("headline"),
                    "model": row["model"],
                    "url": row["url"],
                    "days_since": row["days"],
                    "updated_at": row.get("at"),
                    "next_label": row.get("next_label"),
                    "next_date": row.get("next_date"),
                    "next_confidence": row.get("next_confidence"),
                    "next_url": row.get("next_url"),
                    "via": row["via"],
                    "open_weights": row["weights"],
                    "summary_ko": None,
                    "heat": float(-(row["days"] if row["days"] is not None else 999)),
                    "source_count": 1,
                    "sources": [{"name": row["via"] or "-"}],
                    "change": "new" if (row["days"] or 99) <= 1 else "continuing",
                    "dedup_key": f"vendor:{row['vendor']}:{row.get('family') or '-'}",
                    "published_at": None,
                })
            if not cards:
                empty_reason = "벤더 현황을 가져오지 못했습니다."

        elif sid == "github_skills":
            for row in github_rows:
                seq += 1
                key = row["repo"]
                cards.append({
                    "id": f"c_{board_date}_{seq:03d}",
                    "title": row["title"],
                    "summary_ko": None,
                    "url": row["url"],
                    # 스타 증가분을 그대로 넣으면 뉴스 화제도(한 자릿수)와 자릿수가
                    # 안 맞는다. 정렬 순서는 stars_delta 가 이미 정했으므로
                    # heat 는 로그로 눌러 비슷한 눈금에 올린다.
                    # 증가분을 못 구한 폴백에서는 None 이 온다. 그때는
                    # 누적 스타로 줄을 세우되 자릿수는 같은 눈금에 올린다.
                    "heat": round(math.log10(
                        1 + (row["stars_delta"]
                             if row["stars_delta"] is not None
                             else (row.get("stars") or 0))) * 3, 2),
                    "source_count": 1,
                    "sources": [{"name": "GitHub"}],
                    "change": "continuing" if key in prev_keys else "new",
                    "dedup_key": key,
                    "published_at": None,
                    "repo": row["repo"],
                    "stars": row["stars"],
                    "stars_delta": row["stars_delta"],
                    "category": row["category"],
                    "kind": row.get("kind", "스킬"),
                    "updated_at": row.get("pushed_at") or None,
                    # 영어 원문 설명. LLM 키가 생기면 summary_ko 가 위에 붙는다.
                    "desc": row.get("desc") or None,
                    "note_ko": notes_map.get(row["repo"]),
                })
            if not cards:
                empty_reason = "GitHub 응답이 없어 오늘은 비어 있습니다."

        elif sid == "communities":
            # 두 숫자의 성격이 다르다. mentions 는 AI에 한정된 우리 측정치이고,
            # rank 는 그 사이트 전체 규모다. 화면에서도 이 차이를 숨기지 않는다.
            for row in (community_rows or []):
                seq += 1
                cards.append({
                    "id": f"c_{board_date}_{seq:03d}",
                    "title": row["name"],
                    "summary_ko": None,
                    "url": f"https://{row['domain']}",
                    "heat": float(row.get("mentions") or 0),
                    "source_count": 1,
                    "sources": [{"name": "Tranco"}],
                    "change": "continuing" if row["domain"] in prev_keys else "new",
                    "dedup_key": row["domain"],
                    "published_at": None,
                    "domain": row["domain"],
                    "mentions": row.get("mentions") or 0,
                    "engagement": row.get("engagement") or 0,
                    "region": row.get("region", "global"),
                    # Tranco 전체 순위는 뺐다 — reddit.com 순위는 레딧 전체의 것이지
                    # AI 대화의 것이 아니라서, 사용자가 "애매하다"고 한 바로 그 지점이다.
                    # 대신 각 커뮤니티가 실제로 공개하는 숫자를 단위와 함께 싣는다.
                    "signal_kind": row.get("signal_kind"),
                    "signal_value": row.get("signal_value"),
                    "note": row.get("note"),
                })
            if not cards:
                empty_reason = "커뮤니티 신호를 수집하지 못했습니다."

        elif sid == "keywords":
            for row in (keyword_rows or []):
                seq += 1
                cards.append({
                    "id": f"k_{board_date}_{seq:03d}",
                    "keyword": row["keyword"],
                    "keyword_ko": row.get("keyword_ko"),
                    "mentions": row.get("mentions") or 0,
                    "source_count": row.get("source_count") or 0,
                    "items": row.get("items") or [],
                    "change": ("continuing" if row["keyword"].lower() in prev_keys
                               else "new"),
                    "dedup_key": row["keyword"].lower(),
                })
            if not cards:
                empty_reason = "오늘 반복해서 나온 주제가 없습니다."

        else:
            pool = clusters_by_section.get(sid, [])
            groups = ([("global", PER_REGION), ("kr", PER_REGION)]
                      if sid == "top_headlines" else [(None, PER_SECTION)])
            for region, limit in groups:
                used, taken = {}, 0
                for cluster in pool:
                    if taken >= limit:
                        break
                    if region and cluster.get("region", "global") != region:
                        continue
                    lead = cluster["sources"][0] if cluster["sources"] else "?"
                    # 출처가 여러 곳인 묶음은 한 매체의 것이 아니므로 제한하지 않는다
                    if cluster["source_count"] == 1 and used.get(lead, 0) >= MAX_PER_SOURCE:
                        continue
                    used[lead] = used.get(lead, 0) + 1
                    seq += 1
                    card = _card(cluster, seq, board_date, prev_keys)
                    card["region"] = cluster.get("region", "global")
                    hit = news_notes.get(card["dedup_key"]) or {}
                    if isinstance(hit, str):        # 옛 형식: 한 줄 문자열
                        hit = {"note": hit}
                    card["note_ko"] = hit.get("note")
                    # 해외 기사는 한국어 제목을 기본으로 둔다. 없으면 원문이 남는다 —
                    # 빈 제목보다 원문이 낫다.
                    if card["region"] == "global":
                        card["title_ko"] = hit.get("title_ko")
                    cards.append(card)
                    taken += 1
            if not cards:
                empty_reason = ("오늘은 새로 나온 모델이 없습니다."
                                if sid == "model_updates"
                                else "수집된 항목이 없습니다.")

        extra = {}
        if sid == "model_updates" and milestone:
            # 마일스톤은 현황판 위에 올라가는 1년 축이다. 섹션에 얹어 보낸다.
            extra["milestone"] = milestone
        sections.append({
            "id": sid,
            "title": SECTION_TITLES[sid],
            **extra,
            "briefing_ko": [],          # 섹션 브리핑도 LLM 몫
            "empty_reason": empty_reason,
            "cards": cards,
        })

    ok_sources = sum(1 for s in sources_status if s["ok"])
    collected = sum(s.get("items", 0) for s in sources_status)
    failed = len(sources_status) - ok_sources

    if failed == 0:
        status = "ok"
    elif collected < 20:
        status = "degraded"
    else:
        status = "partial"

    return {
        "schema_version": SCHEMA_VERSION,
        "board_date": board_date,
        "generated_at": _iso(now),
        "status": status,
        "previous_board_date": (prev or {}).get("board_date"),
        "generator": {
            "pipeline_version": "0.1.0",
            "model": None,
            "counts": {
                "collected": collected,
                "clustered": sum(len(v) for v in clusters_by_section.values()),
                "published": sum(len(s["cards"]) for s in sections),
            },
            "api_budget": budget_report,
            "notes": notes or [],
        },
        "sources_status": sources_status,
        "sections": sections,
    }


def write(board, boards_dir, keep_days=14):
    os.makedirs(boards_dir, exist_ok=True)
    dated = os.path.join(boards_dir, f"{board['board_date']}.json")
    for path in (dated, os.path.join(boards_dir, "latest.json")):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(board, fh, ensure_ascii=False, indent=2)

    # 색인: 90일치 상태만. 파이프라인이 얼마나 자주 성공하는지 확인용.
    index_path = os.path.join(boards_dir, "index.json")
    try:
        with open(index_path, encoding="utf-8") as fh:
            index = json.load(fh)
    except Exception:
        index = []
    index = [row for row in index if row.get("date") != board["board_date"]]
    index.append({
        "date": board["board_date"],
        "status": board["status"],
        "counts": board["generator"]["counts"],
    })
    index.sort(key=lambda r: r["date"], reverse=True)
    index = index[:90]
    with open(index_path, "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=2)

    # 보관: 전체 보드는 14일치만 남긴다
    kept = {row["date"] for row in index[:keep_days]}
    for name in os.listdir(boards_dir):
        if name in ("latest.json", "index.json") or not name.endswith(".json"):
            continue
        if name[:-5] not in kept:
            os.remove(os.path.join(boards_dir, name))

    return dated
