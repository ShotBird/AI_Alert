"""GitHub 스킬 섹션.

티켓 10에서 확인된 것: GitHub 에 스타 히스토리 전용 엔드포인트가 있다.

    GET /repos/{owner}/{repo}/stargazers/history

주별 총계를 최신순으로 주므로 **7일 증가분을 그대로 읽는다.** 스냅샷을 쌓을 필요가 없고
첫날부터 진짜 주간 랭킹이 나온다. 이 엔드포인트는 search 가 아니라 core 버킷을 쓴다
(무인증 시간당 60회, 인증 5,000회 — 헤더로 확인).

티켓 06에서 확인된 것: 상위 레포의 62%가 랭킹에 쓸 수 없다.
모음집 35%, 토픽만 달아둔 무관 제품 20%, 설명 없음 7%.
그래서 **랭킹에 넣기 전에 걸러낸다.**
"""

import json
import re
import urllib.error
import urllib.request

from .budget import BudgetExceeded

API = "https://api.github.com"
UA = "ai-alert/0.1 (personal daily digest)"

TOPICS = ["agent-skills", "claude-skills"]

# 모음집 판별. LLM 분류가 붙기 전까지 쓰는 규칙 기반 1차 필터다.
COLLECTION_RE = re.compile(
    r"\b(awesome|collection|curated|directory|marketplace|registry|list of|"
    r"\d{2,}\+?\s*(skills|agents|prompts|plugins|commands)|monorepo of)\b", re.I)

# 에이전트 스킬이 아닌데 토픽만 달아둔 것들을 거르기 위한 최소 조건.
SKILL_HINT_RE = re.compile(r"\b(skill|skills|agent|claude|codex|mcp|plugin)\b", re.I)


def _get(url, token=None):
    headers = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _classify(repo):
    """부문 배지. 설명과 토픽에서 규칙으로 정한다.

    티켓 06 결론: 토픽 태그만으로는 안 된다(도구 이름에 지배당한다).
    제대로 하려면 LLM 한 번 패스가 필요하고, 그건 API 키가 생기면 붙인다.
    여기 있는 건 그때까지 쓰는 근사값이다.
    """
    blob = f"{repo.get('description') or ''} {' '.join(repo.get('topics') or [])}".lower()
    table = [
        ("디자인·비주얼", ("design", "diagram", "ui", "ux", "figma", "slide", "ppt", "video", "image")),
        ("글쓰기·콘텐츠", ("writing", "writer", "content", "novel", "blog", "copy", "humaniz")),
        ("메모리·컨텍스트", ("memory", "context", "rag", "knowledge", "recall")),
        ("마케팅·SEO", ("seo", "marketing", "growth", "ads", "social")),
        ("비즈니스·금융", ("finance", "invoice", "legal", "ecommerce", "business", "accounting")),
        ("인프라·백엔드", ("terraform", "aws", "kubernetes", "docker", "postgres", "database",
                        "backend", "devops", "cloud", "golang", "dotnet")),
        ("연구·과학", ("research", "paper", "science", "arxiv", "bio", "chem")),
        ("보안", ("security", "pentest", "ctf", "vulnerab", "audit")),
        ("브라우저 자동화", ("browser", "scrap", "crawl", "playwright", "selenium")),
        ("스킬 제작", ("skill-creator", "skill creator", "authoring", "template", "scaffold")),
        ("계획·오케스트레이션", ("plan", "planning", "orchestrat", "workflow", "roadmap", "task")),
    ]
    for label, needles in table:
        # 단어 경계로 본다. 부분 문자열로 보면 "ui" 가 build/guide/require 에 걸린다.
        if any(re.search(r"(?<![a-z])" + re.escape(n), blob) for n in needles):
            return label
    return "기타"


def _usable(repo):
    desc = (repo.get("description") or "").strip()
    if not desc:
        return False, "설명 없음"
    if COLLECTION_RE.search(desc) or COLLECTION_RE.search(repo.get("name", "")):
        return False, "모음집"
    blob = f"{desc} {' '.join(repo.get('topics') or [])}"
    if not SKILL_HINT_RE.search(blob):
        return False, "무관 제품"
    return True, None


def weekly_delta(full_name, token, budget):
    """지난 7일 스타 증가분. 못 구하면 None."""
    budget.check("github_core")
    try:
        hist = _get(f"{API}/repos/{full_name}/stargazers/history?per_page=2", token)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError):
        return None
    finally:
        budget.spend("github_core")
    if not isinstance(hist, list) or not hist:
        return None
    # 최신순. [0]은 진행 중인 주라 짧고, [1]이 직전 한 주 전체다.
    if len(hist) >= 2:
        return (hist[0].get("total") or 0) + (hist[1].get("total") or 0)
    return hist[0].get("total") or 0


def top_rising(token, budget, candidates=40, want=5):
    """부문 배지가 달린 상위 급상승 스킬."""
    pool, seen, notes = [], set(), []

    for topic in TOPICS:
        try:
            budget.check("github_search")
        except BudgetExceeded:
            break
        url = (f"{API}/search/repositories?q=topic:{topic}"
               f"&sort=stars&order=desc&per_page=50")
        try:
            data = _get(url, token)
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
            notes.append(f"{topic}: {type(exc).__name__}")
            continue
        finally:
            budget.spend("github_search")

        for repo in data.get("items", []):
            name = repo.get("full_name")
            if not name or name in seen:
                continue
            seen.add(name)
            ok, _why = _usable(repo)
            if ok:
                pool.append(repo)

    # 후보를 너무 많이 잡으면 core 예산을 태운다. 누적 스타 상위부터 본다.
    pool = pool[:candidates]

    rows = []
    for repo in pool:
        try:
            delta = weekly_delta(repo["full_name"], token, budget)
        except BudgetExceeded:
            notes.append("core 예산 도달, 남은 후보는 건너뜀")
            break
        if delta is None:
            continue
        rows.append(dict(
            repo=repo["full_name"],
            title=repo["full_name"],
            url=repo.get("html_url"),
            summary_src=repo.get("description") or "",
            stars=repo.get("stargazers_count") or 0,
            stars_delta=delta,
            category=_classify(repo),
        ))

    rows.sort(key=lambda r: r["stars_delta"], reverse=True)
    return rows[:want], notes
