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
    # 구체적인 것부터 본다. "code review" 가 "backend" 보다 먼저 걸려야
    # alibaba/open-code-review 가 인프라로 뭉뚱그려지지 않는다.
    table = [
        ("다이어그램",     ("diagram", "mermaid", "flowchart", "architecture diagram", "excalidraw")),
        ("디자인·UI",     ("design", "figma", "design-system", "design token", "ux", "wireframe", "css")),
        ("슬라이드·문서",  ("slide", "ppt", "powerpoint", "pptx", "keynote", "docx", "pdf", "report")),
        ("이미지·영상",    ("image", "video", "photo", "render", "thumbnail", "sora", "diffusion")),
        ("코드리뷰",       ("code review", "code-review", "review", "pr review", "lint", "refactor")),
        ("테스트·품질",    ("test", "testing", "tdd", "coverage", "e2e", "playwright test", "qa")),
        ("프론트엔드",     ("react", "vue", "svelte", "solidjs", "next.js", "frontend", "tailwind", "web performance")),
        ("백엔드·API",    ("api", "rest", "graphql", "backend", "microservice", "grpc", "fastapi", "django")),
        ("데이터베이스",   ("postgres", "mysql", "sqlite", "mongodb", "redis", "database", "sql", "migration")),
        ("인프라·배포",    ("terraform", "kubernetes", "docker", "aws", "gcp", "azure", "devops", "ci/cd", "deploy")),
        ("보안",          ("security", "pentest", "ctf", "vulnerab", "audit", "exploit", "owasp")),
        ("브라우저 자동화", ("browser", "playwright", "selenium", "puppeteer", "automation")),
        ("크롤링·수집",    ("scrap", "crawl", "spider", "extract", "rss")),
        ("RAG·검색",      ("rag", "retrieval", "vector", "embedding", "semantic search", "index")),
        ("메모리·컨텍스트", ("memory", "context", "knowledge", "recall", "session", "compaction")),
        ("글쓰기",        ("writing", "writer", "novel", "screenplay", "copywriting", "humaniz", "blog post")),
        ("번역·언어",     ("translat", "i18n", "localization", "번역")),
        ("마케팅·SEO",    ("seo", "marketing", "growth", "ads", "social media", "newsletter")),
        ("데이터·분석",    ("analytics", "dashboard", "pandas", "notebook", "visualiz", "chart", "etl")),
        ("금융·회계",     ("finance", "invoice", "accounting", "trading", "stock", "tax", "budget")),
        ("법률·규정",     ("legal", "contract", "compliance", "gdpr", "license")),
        ("연구·논문",     ("research", "paper", "arxiv", "citation", "literature")),
        ("과학·바이오",    ("bio", "chem", "genom", "protein", "physics", "medical", "clinical")),
        ("스킬 제작",      ("skill-creator", "skill creator", "authoring", "scaffold", "boilerplate", "generator")),
        ("에이전트 운영",  ("orchestrat", "multi-agent", "swarm", "subagent", "mcp server", "tool use")),
        ("계획·관리",     ("plan", "planning", "roadmap", "task", "ticket", "issue", "project management", "sprint")),
    ]
    for label, needles in table:
        # 단어 경계로 본다. 부분 문자열로 보면 "ui" 가 build/guide 에 걸린다.
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


class RateLimited(Exception):
    """GitHub 레이트리밋. 데이터가 없는 것과 구별해야 한다.

    이 둘을 같은 None 으로 뭉개는 바람에 섹션이 "응답이 없어 비어 있습니다"라고
    거짓말을 했다. 실제로는 우리가 시간당 60회를 다 쓴 것이었다.
    """


def weekly_delta(full_name, token, budget, cache=None):
    """지난 7일 스타 증가분. 데이터가 없으면 None, 한도 초과면 RateLimited."""
    if cache is not None and full_name in cache:
        return cache[full_name]

    budget.check("github_core")
    try:
        hist = _get(f"{API}/repos/{full_name}/stargazers/history?per_page=2", token)
    except urllib.error.HTTPError as exc:
        # 403 + Remaining: 0 이면 한도 초과다. 권한 문제와도 구별된다.
        if exc.code in (403, 429) and exc.headers.get("X-RateLimit-Remaining") == "0":
            raise RateLimited(exc.headers.get("X-RateLimit-Resource") or "core") from exc
        return None
    except (urllib.error.URLError, ValueError):
        return None
    finally:
        budget.spend("github_core")

    if not isinstance(hist, list) or not hist:
        return None
    # 최신순. [0]은 진행 중인 주라 짧고, [1]이 직전 한 주 전체다.
    if len(hist) >= 2:
        value = (hist[0].get("total") or 0) + (hist[1].get("total") or 0)
    else:
        value = hist[0].get("total") or 0
    if cache is not None:
        cache[full_name] = value
    return value


def top_rising(token, budget, candidates=60, want=20, cache=None):
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

    def row(repo, delta):
        return dict(
            repo=repo["full_name"],
            title=repo["full_name"],
            url=repo.get("html_url"),
            desc=(repo.get("description") or "").strip(),
            pushed_at=(repo.get("pushed_at") or "")[:10],
            stars=repo.get("stargazers_count") or 0,
            stars_delta=delta,
            category=_classify(repo),
        )

    rows, limited = [], False
    for repo in pool:
        try:
            delta = weekly_delta(repo["full_name"], token, budget, cache)
        except BudgetExceeded:
            notes.append("GitHub 호출 상한에 닿아 남은 후보는 건너뜁니다.")
            break
        except RateLimited:
            limited = True
            break
        if delta is None:
            continue
        rows.append(row(repo, delta))

    if limited:
        # 여기서 빈 섹션을 돌려주면 화면이 "응답이 없다"고 거짓말을 한다.
        # 증가분을 못 구한 것뿐이니, 누적 스타로 줄을 세우고 **그렇다고 밝힌다.**
        # 티켓 10 이 누적 랭킹을 버린 이유(매일 같은 목록)는 여전히 유효하므로
        # 이건 정상 동작이 아니라 폴백이라는 표시를 반드시 달고 나간다.
        notes.append("GitHub 시간당 호출 한도(무인증 60회)를 다 써서 "
                     "주간 증가분 대신 누적 스타로 줄을 세웠습니다. "
                     "GH_READ_TOKEN 을 넣으면 5,000회로 늘어납니다.")
        seen_repos = {r["repo"] for r in rows}
        for repo in pool:
            if len(rows) >= want:
                break
            if repo["full_name"] in seen_repos:
                continue
            rows.append(row(repo, None))

    rows.sort(key=lambda r: (r["stars_delta"] is None,
                             -(r["stars_delta"] or 0),
                             -(r["stars"] or 0)))
    return rows[:want], notes
