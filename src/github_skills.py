"""GitHub 스킬·도구 섹션.

목표는 사용자가 두 번 말한 규칙이다:
**"(종류 × 부문) 칸마다 20개, 전체 정렬은 전 부문을 다 넣고 Top 20."**

두 개의 서로 다른 레이트리밋 위에서 돈다. 이게 이 파일의 전부다.

  search  — 분당 10회(무인증) / 30회(인증). **분마다 리셋된다.**
            기다릴 줄만 알면 후보를 몇천 개까지 모을 수 있다. 칸을 채우는 건
            전부 여기서 한다(_Pacer 참고).
  core    — 시간당 60회(무인증) / 5,000회(인증). **리셋이 한 시간 뒤다.**
            주간 증가분(GET /repos/{o}/{r}/stargazers/history)이 여기 속한다.

칸을 채우는 것과 증가분을 재는 것은 그래서 **완전히 다른 문제다.**

  칸 채우기는 search 로 한다. 여유분이 여기 있다. 1단계는 토픽 14개를 훑고
  (_search_pool), 2단계는 모자란 칸을 종류·부문 어구로 겨냥해 판다(_gap_fill).
  종류 4 × 부문 27 = 108칸이고, 20줄씩이면 2,160줄이 목표다.

  증가분 재기는 core 다. **무인증에서는 한 시간에 60개가 하드 상한이다.**
  2,160줄을 다 재는 것은 토큰 없이는 불가능하다. 숫자를 지어내 메우지 않는다 —
  못 잰 줄은 stars_delta=None 으로 남고, 화면은 그 줄을 '누적'으로 표시하며,
  노트가 몇 개를 실제로 쟀는지 밝힌다. 그래서 이 섹션 제목도 "급상승"이
  아니다(board.GITHUB_SECTION_TITLE).

카드 스키마는 이 섹션만 얇다. 줄이 2천 개가 되면 화면이 안 읽는 필드 하나가
수백 KB다 — board.GITHUB_CARD_FIELDS 와 DESC_MAX 를 보라.

티켓 06에서 확인된 것: 상위 레포의 62%가 랭킹에 쓸 수 없다.
모음집 35%, 토픽만 달아둔 무관 제품 20%, 설명 없음 7%.
그래서 **랭킹에 넣기 전에 걸러낸다.**
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from .budget import BudgetExceeded

API = "https://api.github.com"
UA = "ai-alert/0.1 (personal daily digest)"

# 종류별 토픽. 화면의 첫 축이 이 키가 되고, 부문(디자인·코드리뷰…)이 두 번째 축이다.
# 새 섹션을 만들지 않고 축을 얹는 쪽을 택했다 — 수집·랭킹·화면이 이미 다 있다.
# 토픽을 넷 더 붙였다(claude-code / agentic-framework / agentic-ai / ai-tools).
# 측정해 보고 넣은 것이다 — 기존 목록에 없던 usable 후보가 각각 34~64개 더 나왔고,
# 그중에 dify·AutoGPT·ragflow·plandex 처럼 빠져 있으면 이상한 것들이 들어 있었다.
# search 는 분당 리셋이라 토픽을 늘리는 값이 싸다(호출 8회 = 대기 1분 남짓).
KINDS = {
    "스킬": ["agent-skills", "claude-skills", "claude-code-skills", "claude-code"],
    # 토픽 `mcp` 는 뺐다. 7.8만 레포가 달고 있는 마케팅 태그라, 스타 순으로 100개를
    # 받으면 자바 면접 가이드·웹 UI·데스크톱 런처가 "MCP 서버" 자리를 차지했다.
    # 정확한 두 토픽만 쓰면 상위가 context7·github-mcp-server·chrome-devtools-mcp 로 바뀐다.
    "MCP 서버": ["mcp-server", "model-context-protocol"],
    "에이전트 프레임워크": ["ai-agent", "agent-framework", "llm-agent",
                     "agentic-framework", "agentic-ai"],
    "CLI·개발도구": ["ai-cli", "llm-tools", "ai-coding", "ai-tools"],
}
TOPICS = [t for v in KINDS.values() for t in v]

_TOPIC_KIND = {t: k for k, v in KINDS.items() for t in v}

# 종류 판정에 쓰는 **레포 자신의** 토픽. 검색에 쓴 토픽과 일부러 분리했다.
# 사고: 종류를 "어느 토픽으로 검색해 찾았나"로 정하는 바람에, 홍보용으로 `mcp`
# 태그만 달아둔 대형 레포(n8n·dify·open-webui·JavaGuide)가 전부 "MCP 서버"가 됐다.
# 반대로 설명에 "open-source MCP server"라고 적힌 AIHawk 는 `ai-agent` 토픽으로
# 먼저 걸려 "에이전트 프레임워크"가 됐다. 사용자가 구분하라고 한 바로 그 축이
# 검색 순서에 좌우되고 있었다.
_SKILL_TOPICS = {
    "agent-skills", "agent-skill", "claude-skills", "claude-skill",
    "claude-code-skills", "claude-code-skill", "codex-skills", "agentskills",
}
_FRAMEWORK_TOPICS = {
    "ai-agent", "ai-agents", "agent-framework", "agentic-framework",
    "llm-agent", "llm-agents", "multi-agent", "multi-agent-systems",
    "autonomous-agents", "agent-harness", "agent-orchestration",
}
_CLI_TOPICS = {
    "ai-cli", "llm-tools", "ai-coding", "cli", "command-line", "terminal",
    "tui", "devtools", "developer-tools", "coding-agent", "cli-tool",
}
_MCP_TOPICS = {"mcp-server", "mcp-servers", "model-context-protocol", "mcp"}
# 이름·토픽만으로도 확실한 CLI 신호. 프레임워크 판정보다 먼저 본다 —
# google-gemini/gemini-cli 는 `ai-agent` 토픽도 달고 있어서 순서를 뒤집으면
# "에이전트 프레임워크"가 된다.
_CLI_STRONG_TOPICS = {"ai-cli", "cli", "cli-tool", "command-line", "terminal", "tui"}
_CLI_NAME_RE = re.compile(r"(^|[-_])(cli|tui|shell|term)([-_]|$)", re.I)

# "이 레포가 스스로 MCP 라고 말하는가". 토픽 `mcp` 는 마케팅 태그라 신호가 약해서
# 이름·설명에 MCP 가 단어로 등장할 때만 1순위로 인정한다.
_MCP_SELF_RE = re.compile(r"(?<![a-z])mcp(?![a-z])|model context protocol", re.I)
_SKILL_SELF_RE = re.compile(
    r"agent skill|claude skill|codex skill|skill for (claude|codex|agents?|ai)|"
    r"skills? (pack|library|collection|bundle)", re.I)
_FRAMEWORK_SELF_RE = re.compile(
    r"agent(ic)? framework|framework for (building )?agents?|multi-?agent|"
    r"agent harness|orchestrat", re.I)
_CLI_SELF_RE = re.compile(
    r"(?<![a-z])cli(?![a-z])|command[- ]line|(?<![a-z])tui(?![a-z])|terminal", re.I)


def _detect_kind(repo, fallback):
    """종류(스킬 / MCP 서버 / 에이전트 프레임워크 / CLI·개발도구).

    레포 자신의 토픽과 이름·설명으로 정하고, 아무 신호도 없을 때만 검색 토픽을
    쓴다. 순서가 곧 우선순위다 — 위에 있을수록 강한 신호다.
    """
    topics = {t.lower() for t in (repo.get("topics") or [])}
    blob = f"{repo.get('name') or ''} {repo.get('description') or ''}"

    if _MCP_SELF_RE.search(blob):
        return "MCP 서버"
    if topics & _SKILL_TOPICS or _SKILL_SELF_RE.search(blob):
        return "스킬"
    if topics & _CLI_STRONG_TOPICS or _CLI_NAME_RE.search(repo.get("name") or ""):
        return "CLI·개발도구"
    if topics & _FRAMEWORK_TOPICS or _FRAMEWORK_SELF_RE.search(blob):
        return "에이전트 프레임워크"
    if topics & _CLI_TOPICS or _CLI_SELF_RE.search(blob):
        return "CLI·개발도구"
    if topics & _MCP_TOPICS:
        return "MCP 서버"
    return fallback


# 모음집 판별. LLM 분류가 붙기 전까지 쓰는 규칙 기반 1차 필터다.
# `guide`·`checklist` 계열을 뒤늦게 넣었다. Snailclimb/JavaGuide(자바 면접 가이드)와
# thedaviddias/Front-End-Checklist 가 `mcp`·`ai-agent` 토픽만 달고 상위에 올라와
# "MCP 서버 / 디자인·UI" 같은 자리를 차지했다. 둘 다 읽을거리 모음이지 도구가 아니다.
COLLECTION_RE = re.compile(
    r"\b(awesome|collection|curated|directory|marketplace|registry|list of|"
    r"guides?|checklist|cheat ?sheet|handbook|roadmap|tutorials?|"
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


# 부문 표. **순서가 곧 우선순위다** — 구체적인 것부터 본다.
# "code review" 가 "backend" 보다 먼저 걸려야 alibaba/open-code-review 가
# 인프라로 뭉뚱그려지지 않는다.
#
# 이 표를 모듈 상수로 끌어낸 이유는 하나다: 칸 채우기(_gap_fill)가 "어떤 부문들이
# 있는가"를 알아야 하는데, 함수 안에 갇혀 있으면 목록을 **한 번 더 적게 된다.**
# 두 벌이 되는 순간 조용히 갈라진다. 부문 이름을 바꾸거나 더하지는 않는다 —
# 사용자가 분류 체계는 그대로 두라고 했다.
CATEGORY_TABLE = [
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
# "기타"는 표에 없다 — 아무것도 안 걸렸을 때의 값이라 겨냥해 검색할 수 없다.
CATEGORIES = [label for label, _ in CATEGORY_TABLE] + ["기타"]


def _classify(repo):
    """부문 배지. 설명과 토픽에서 규칙으로 정한다.

    티켓 06 결론: 토픽 태그만으로는 안 된다(도구 이름에 지배당한다).
    제대로 하려면 LLM 한 번 패스가 필요하고, 그건 API 키가 생기면 붙인다.
    여기 있는 건 그때까지 쓰는 근사값이다.
    """
    blob = f"{repo.get('description') or ''} {' '.join(repo.get('topics') or [])}".lower()
    for label, needles in CATEGORY_TABLE:
        # 단어 경계로 본다. 부분 문자열로 보면 "ui" 가 build/guide 에 걸린다.
        if any(re.search(r"(?<![a-z])" + re.escape(n), blob) for n in needles):
            return label
    return "기타"


# 레포 **이름**에는 단어 경계가 없다 — "JavaGuide"·"AwesomeMCP" 처럼 붙여 쓴다.
# 그래서 이름은 경계 없는 별도 패턴으로 본다. 설명에 이걸 쓰면 오탐이 난다.
NAME_COLLECTION_RE = re.compile(
    r"awesome|guide|checklist|handbook|cheat-?sheet|cookbook|roadmap|tutorial", re.I)


def _usable(repo):
    desc = (repo.get("description") or "").strip()
    if not desc:
        return False, "설명 없음"
    name = repo.get("name", "")
    if COLLECTION_RE.search(desc) or COLLECTION_RE.search(name):
        return False, "모음집"
    if NAME_COLLECTION_RE.search(name):
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


# GitHub search 는 core 와 **다른 버킷**이고 분당으로 리셋된다(무인증 10/분,
# 인증 30/분). core 처럼 시간당 60회로 묶여 있지 않으므로, 기다릴 줄만 알면
# 후보 풀을 몇 배로 키울 수 있다. 여기가 이 섹션의 유일한 여유분이다.
SEARCH_WINDOW = 62.0        # 초. 분 경계를 넘겨 잡아 경계에서 걸리지 않게 한다
SEARCH_BURST_ANON = 9       # 10/분 중 한 칸은 비워둔다
SEARCH_BURST_AUTH = 28


class _Pacer:
    """search 레이트리밋을 우리가 먼저 지킨다.

    사고: 토픽 12개를 쉬지 않고 연달아 부르면 11번째부터 403이 떨어져
    마지막 두 토픽(llm-tools·ai-coding)이 통째로 빠졌다. 그 둘이
    CLI·개발도구 종류의 2/3라, 그 종류만 조용히 굶고 있었다
    (2026-09-21 보드의 CLI 카드는 전부 스타 2,000 미만이었다).
    """

    def __init__(self, burst, sleeper=None, clock=None):
        self.burst = burst
        self.sleeper = sleeper or time.sleep
        self.clock = clock or time.monotonic
        self.stamps = []

    def wait(self):
        now = self.clock()
        self.stamps = [t for t in self.stamps if now - t < SEARCH_WINDOW]
        if len(self.stamps) >= self.burst:
            self.sleeper(max(SEARCH_WINDOW - (now - self.stamps[0]), 1.0))
            now = self.clock()
            self.stamps = [t for t in self.stamps if now - t < SEARCH_WINDOW]
        self.stamps.append(now)

    def cooldown(self):
        """403 을 맞았다. 다음 호출 전에 한 창을 통째로 쉰다.

        사고(2026-09-21 실측): 9/62초를 지켰는데도 20분짜리 회차 중간에 403 이
        세 번 떨어졌다(GitHub 의 2차 제한으로 보인다). 그런데 실패한 칸은
        개수가 그대로라 바로 다음 순번에 **또 같은 칸이 뽑혀** 곧장 다시 두드렸고,
        그 칸의 질의 3개를 연달아 403 으로 날렸다. 실패는 "더 빨리 다시 해보라"는
        뜻이 아니다 — 창을 채워 두어 다음 wait() 가 반드시 쉬게 한다."""
        now = self.clock()
        self.stamps = [now] * self.burst


class _SearchStop(Exception):
    """검색 예산이 끝났다. 남은 계획을 조용히 접는다."""


def _search(query, token, budget, notes, pacer, label):
    """검색 한 번. (items, total_count) 또는 실패하면 (None, None).

    예산·페이서·오류 처리를 여기 한 곳에 모았다. 두 벌로 갈라져 있으면
    한쪽만 페이서를 안 쓰는 사고가 난다 — 실제로 그렇게 403 을 먹었다.
    """
    try:
        budget.check("github_search")
    except BudgetExceeded:
        raise _SearchStop() from None
    pacer.wait()
    url = (f"{API}/search/repositories?q={urllib.parse.quote(query, safe=':')}"
           f"&sort=stars&order=desc&per_page=100&page=1")
    try:
        data = _get(url, token)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
        code = getattr(exc, "code", None)
        notes.append(f"{label}: 검색 실패 ({type(exc).__name__}"
                     f"{f' {code}' if code else ''}) — 이 질의는 빠졌습니다.")
        return None, None
    finally:
        budget.spend("github_search")
    return data.get("items", []), data.get("total_count")


def _absorb(items, pool, seen, buckets, fallback_kind):
    """검색 결과를 후보 풀과 칸에 넣는다. 이미 본 레포는 건너뛴다."""
    added = 0
    for repo in items or []:
        name = repo.get("full_name")
        if not name or name in seen:
            continue
        seen.add(name)
        if not _usable(repo)[0]:
            continue
        repo["_kind"] = _detect_kind(repo, fallback_kind)
        pool.append(repo)
        buckets.setdefault((repo["_kind"], _classify(repo)), []).append(repo)
        added += 1
    return added


def _search_pool(token, budget, notes, pages, pacer, pool, seen, buckets):
    """토픽별 검색 결과를 모아 쓸 만한 후보만 남긴다. 1단계(넓게 훑기).

    종류(kind)는 **찾은 토픽이 아니라 레포 자신의 신호**로 정한다. 검색 토픽은
    아무 신호도 없을 때의 마지막 수단으로만 쓴다.
    """
    spent = 0
    for topic in TOPICS:
        for page in range(1, pages + 1):
            try:
                budget.check("github_search")
            except BudgetExceeded:
                notes.append("GitHub 검색 상한에 닿아 남은 토픽은 건너뜁니다.")
                return spent
            pacer.wait()
            url = (f"{API}/search/repositories?q=topic:{topic}"
                   f"&sort=stars&order=desc&per_page=100&page={page}")
            try:
                data = _get(url, token)
            except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
                code = getattr(exc, "code", None)
                notes.append(f"{topic}: 검색 실패 ({type(exc).__name__}"
                             f"{f' {code}' if code else ''}) — 이 토픽은 빠졌습니다.")
                break
            finally:
                budget.spend("github_search")
                spent += 1

            items = data.get("items", [])
            _absorb(items, pool, seen, buckets, _TOPIC_KIND.get(topic, "스킬"))
            if len(items) < 100:
                break
    return spent


# ---------------------------------------------------------------------------
# 2단계: 칸 채우기(gap fill)
# ---------------------------------------------------------------------------
# 1단계는 토픽 14개를 스타 순으로 훑는다. 그러면 인기 부문(백엔드·보안·디자인)은
# 넘치고 니치 부문(번역·법률·과학)은 굶는다. **검색에 그 레포들이 없어서가 아니라
# 우리가 물어본 적이 없어서다.** 실측(2026-09-21):
#
#   "mcp diagram mermaid"      → 그 칸에 딱 맞는 후보 84개 (그때 우리 칸은 3개)
#   "mcp translation"          → 25개 (우리 칸은 0개)
#   "cli agent translation"    → 33개 (우리 칸은 0개)
#   "claude skill seo marketing" → 19개 (우리 칸은 6개)
#
# 반대로 진짜로 없는 칸도 있다. "cli agent legal contract" 는 GitHub 전체에서
# 3건이다. 그런 칸은 **짧은 채로 둔다** — 안 맞는 레포로 20개를 채우면
# 부문 배지가 거짓말이 되고, 짧은 목록보다 틀린 목록이 나쁘다.
#
# `topic:` 한정자를 붙이는 쪽도 재봤지만 훨씬 나빴다("topic:ai-cli scraping" → 0건).
# 토픽은 소수만 달기 때문에 니치에서는 교집합이 비어버린다. 자유어가 이긴다.

# 종류를 겨냥하는 어구. _detect_kind 가 이름·설명에서 읽어내는 신호를 그대로 쓴다.
# CLI 쪽에 "agent"를 넣은 것은 의도적이다 — _usable 의 SKILL_HINT_RE 가
# skill/agent/claude/mcp/plugin 중 하나를 요구해서, 순수 "cli" 질의는
# 결과의 2/3이 무관 제품으로 걸러진다(측정: usable 23/72 → 75/100).
KIND_TERMS = {
    "스킬": ["claude skill", "agent skill"],
    "MCP 서버": ["mcp server", "mcp"],
    "에이전트 프레임워크": ["ai agent", "agent framework"],
    "CLI·개발도구": ["cli agent", "llm cli"],
}

# 부문을 겨냥하는 어구. CATEGORY_TABLE 의 needle 을 그대로 쓰지 않고 검색어로
# 자연스러운 형태로 적는다 — GitHub 검색은 정규식이 아니라 토큰 매칭이라
# "translat" 같은 어간으로는 아무것도 안 나온다.
CATEGORY_TERMS = {
    "다이어그램": ["diagram mermaid", "architecture diagram", "excalidraw flowchart"],
    "디자인·UI": ["figma design", "design system ui", "ux wireframe"],
    "슬라이드·문서": ["powerpoint slides", "pptx docx", "pdf report document"],
    "이미지·영상": ["image generation", "video render", "thumbnail photo"],
    "코드리뷰": ["code review", "pull request review", "lint refactor"],
    "테스트·품질": ["testing tdd", "e2e test", "test coverage qa"],
    "프론트엔드": ["react frontend", "vue svelte", "tailwind css component"],
    "백엔드·API": ["rest api backend", "graphql api", "fastapi django"],
    "데이터베이스": ["postgres database", "mysql sqlite", "mongodb redis"],
    "인프라·배포": ["kubernetes docker", "terraform devops", "aws deploy"],
    "보안": ["security vulnerability", "pentest exploit", "owasp audit"],
    "브라우저 자동화": ["browser automation", "playwright selenium", "puppeteer browser"],
    "크롤링·수집": ["web scraping", "crawler spider", "rss extract"],
    "RAG·검색": ["rag retrieval", "vector embedding", "semantic search"],
    "메모리·컨텍스트": ["memory context", "knowledge recall", "session memory"],
    "글쓰기": ["writing writer", "novel screenplay", "copywriting blog"],
    "번역·언어": ["translation", "i18n localization", "translate language"],
    "마케팅·SEO": ["seo marketing", "growth ads", "social media newsletter"],
    "데이터·분석": ["analytics dashboard", "pandas notebook", "data visualization chart"],
    "금융·회계": ["finance trading", "invoice accounting", "stock tax"],
    "법률·규정": ["legal contract", "compliance gdpr", "law regulation"],
    "연구·논문": ["research paper arxiv", "citation literature", "academic research"],
    "과학·바이오": ["bioinformatics", "chemistry protein", "medical clinical"],
    "스킬 제작": ["skill creator", "scaffold boilerplate", "authoring generator"],
    "에이전트 운영": ["orchestration swarm", "subagent multi-agent", "tool use runtime"],
    "계획·관리": ["planning task", "project management sprint", "roadmap ticket issue"],
}


def _pair_queries(kind, category):
    """(종류, 부문) 칸 하나를 겨냥한 질의들. 앞에 올수록 잘 맞는다."""
    cats = CATEGORY_TERMS.get(category) or []
    kinds = KIND_TERMS.get(kind) or []
    if not cats or not kinds:
        return []
    # 대각선 순서. (부문어구0×종류어구0) → (0×1) → (1×0) … 로 퍼져서
    # 한 칸에 질의를 여러 번 쓸 때 같은 축만 바꾸지 않는다.
    ranked = sorted(((ci + ki, ci, ki) for ci in range(len(cats))
                     for ki in range(len(kinds))))
    return [f"{kinds[ki]} {cats[ci]}" for _s, ci, ki in ranked]


def _gap_fill(buckets, pool, seen, token, budget, notes, pacer, want, max_requests):
    """모자란 칸을 겨냥해 검색한다. 가장 비어 있는 칸부터 한 질의씩.

    한 질의의 결과는 겨냥한 칸만 채우는 게 아니라 풀 전체로 들어간다
    (예: "mcp diagram" 결과에 스킬·프레임워크도 섞여 있다). 그래서 매번 다시
    세고 다음으로 비어 있는 칸을 고른다 — 필요한 질의 수가 그만큼 줄어든다.

    돌려주는 evidence 는 칸마다 "GitHub 이 그 질의에 몇 건 있다고 답했는가"의
    최대값이다. 짧게 끝난 칸이 **진짜로 얇은지** 말하려면 이 숫자가 있어야 한다.
    """
    pending = {}
    for kind in KINDS:
        for category in CATEGORIES:
            queries = _pair_queries(kind, category)
            if queries:
                pending[(kind, category)] = queries
    # 실패는 따로 모은다. 질의 140개가 전부 403 이면 섹션 노트가 실패 목록
    # 140줄이 된다 — 화면에서 그건 설명이 아니라 고장이다.
    evidence, spent, fails, misses = {}, 0, [], 0
    while spent < max_requests:
        hungry = sorted((len(buckets.get(key, [])), key)
                        for key, queries in pending.items()
                        if queries and len(buckets.get(key, [])) < want)
        if not hungry:
            break
        key = hungry[0][1]
        kind, category = key
        query = pending[key].pop(0)
        try:
            items, total = _search(query, token, budget, fails, pacer,
                                   f"{kind}/{category}")
        except _SearchStop:
            notes.append("GitHub 검색 상한에 닿아 남은 칸은 더 파지 못했습니다.")
            break
        spent += 1
        if items is None:
            pacer.cooldown()
            misses += 1
            if misses >= 5:
                notes.append("GitHub 검색이 연속으로 거절해 칸 채우기를 멈췄습니다.")
                break
            continue
        misses = 0
        if total is not None:
            evidence[key] = max(evidence.get(key, 0), total)
        _absorb(items, pool, seen, buckets, kind)
    if fails:
        notes.append(f"칸 겨냥 검색 {len(fails)}회가 실패했습니다 — {fails[0]}")
    return spent, evidence


# 설명 길이 상한. 한 줄 소개라 원래 짧지만 351자짜리도 온다.
# 화면(.g-desc)은 한 줄로 그리고, 카드 1,160장 기준 desc 가 섹션의 184KB 중
# 가장 큰 항목이었다. 160자면 휴대폰 두 줄이고 뒤는 어차피 안 읽힌다.
DESC_MAX = 160


def _trim_desc(text):
    text = " ".join((text or "").split())
    if len(text) <= DESC_MAX:
        return text
    return text[:DESC_MAX - 1].rstrip() + "…"


def _row(repo, delta):
    # title 은 넣지 않는다 — 1,160장 전부에서 repo 와 글자 하나까지 같았다.
    # 같은 값을 두 번 실어 보내면 카드당 35바이트가 그냥 버려진다.
    return dict(
        repo=repo["full_name"],
        url=repo.get("html_url"),
        desc=_trim_desc(repo.get("description")),
        pushed_at=(repo.get("pushed_at") or "")[:10],
        stars=repo.get("stargazers_count") or 0,
        stars_delta=delta,
        category=_classify(repo),
        kind=repo.get("_kind", "스킬"),
    )


# 칸 채우기에 쓸 검색 횟수의 상한. 무인증 search 는 분당 10회라 시간이 곧 비용이다
# (여기 140 + 1단계 28 ≈ 19분). 토큰이 있으면 분당 30회라 같은 일이 6분에 끝나므로
# 더 파도 된다. 돈이 드는 호출이 아니고 GitHub 도 검색에 일일 한도를 두지 않는다.
GAP_REQUESTS_ANON = 140
GAP_REQUESTS_AUTH = 260


def top_rising(token, budget, candidates=60, want=20, cache=None,
               pages=None, sleeper=None, clock=None, gap_requests=None):
    """(종류 × 부문) 칸마다 상위 want 개.

    화면의 "전체"는 이 합집합을 증가분으로 다시 줄 세워 위에서 20개를 보여주고
    (전 부문이 후보에 들어간다), 칸을 고르면 그 칸 안에서 20개를 본다.

    세 단계다.
      1) **토픽 훑기**로 후보 풀을 만든다(_search_pool). 인기 부문이 여기서 다 찬다.
      2) **칸 겨냥 검색**으로 모자란 칸을 판다(_gap_fill). 1단계가 니치 부문을
         굶기는 것은 검색에 없어서가 아니라 우리가 안 물어봐서다.
      3) **core 호출**로 주간 증가분을 잰다. 무인증 시간당 60회가 하드 상한이라
         전부는 못 잰다. 그래서 잰 것과 못 잰 것을 섞지 않는다 —
         못 잰 줄은 stars_delta=None 으로 남고 화면에서 '누적'으로 표시된다.
         **숫자를 지어내지 않는다.**
    """
    notes = []
    if pages is None:
        pages = 4 if token else 2
    if gap_requests is None:
        gap_requests = GAP_REQUESTS_AUTH if token else GAP_REQUESTS_ANON
    pacer = _Pacer(SEARCH_BURST_AUTH if token else SEARCH_BURST_ANON,
                   sleeper=sleeper, clock=clock)

    # 칸(종류 × 부문)으로 나눈다. 칸은 1·2단계가 같이 채우므로 풀과 함께 굴린다.
    pool, seen, buckets = [], set(), {}
    base_spent = _search_pool(token, budget, notes, pages, pacer,
                              pool, seen, buckets)
    gap_spent, evidence = _gap_fill(buckets, pool, seen, token, budget, notes,
                                    pacer, want, gap_requests)

    # 칸 안에서 누적 스타 내림차순. 증가분은 아직 모르므로 여기서는 스타가 유일한 근거다.
    for bucket in buckets.values():
        bucket.sort(key=lambda r: -(r.get("stargazers_count") or 0))

    kept_repos = []
    for bucket in buckets.values():
        kept_repos.extend(bucket[:want])

    # 측정 순서: 칸을 큰 것부터 줄 세우고 칸마다 한 개씩 돌아가며 잰다.
    # 앞에서부터 그냥 자르면 가장 큰 칸 하나가 60회를 다 먹고 나머지 칸은
    # 한 줄도 못 잰다. 칸을 먼저 한 바퀴 돌아야 "전 부문이 포함된 Top 20"이 된다.
    order = sorted(buckets.items(),
                   key=lambda kv: -((kv[1][0].get("stargazers_count") or 0)))
    measure_order = []
    for idx in range(want):
        for _key, bucket in order:
            if idx < min(len(bucket), want):
                measure_order.append(bucket[idx])

    deltas, limited, measured = {}, False, 0
    for repo in measure_order[:candidates]:
        try:
            delta = weekly_delta(repo["full_name"], token, budget, cache)
        except BudgetExceeded:
            notes.append("GitHub core 상한에 닿아 남은 후보의 증가분은 재지 않았습니다.")
            break
        except RateLimited:
            limited = True
            break
        if delta is None:
            continue
        deltas[repo["full_name"]] = delta
        measured += 1

    # 정렬 규칙: **잰 줄이 먼저, 증가분 큰 순. 그 다음이 누적 스타 순.**
    # 화면은 이 순서를 그대로 잘라 쓰므로 칸 안의 순서도 같은 규칙이 된다.
    rows = [_row(r, deltas.get(r["full_name"])) for r in kept_repos]
    rows.sort(key=lambda r: (r["stars_delta"] is None,
                             -(r["stars_delta"] or 0),
                             -(r["stars"] or 0)))

    per_cat = {}
    for r in rows:
        key = (r["kind"], r["category"])
        per_cat[key] = per_cat.get(key, 0) + 1

    if limited:
        notes.append(
            f"GitHub 시간당 core 한도(무인증 60회)를 다 써서 {measured}개까지만 "
            "주간 증가분을 쟀습니다. GH_READ_TOKEN 을 넣으면 5,000회가 됩니다.")
    if measured < len(rows):
        notes.append(
            f"주간 증가분을 실제로 잰 것은 {len(rows)}개 중 {measured}개입니다. "
            "나머지는 누적 스타 순이며 화면에 '누적'으로 표시됩니다 — "
            "증가분을 추정해 채워 넣지 않습니다.")
    notes.extend(_fill_notes(per_cat, evidence, want,
                             base_spent + gap_spent, len(pool)))
    return rows, notes


# 한 칸을 겨냥해 GitHub 이 "전부 이만큼"이라고 답한 수가 이 밑이면, 20개를
# 채울 후보가 세상에 없다고 본다. 100 인 이유: 검색 한 쪽이 100개이고,
# 그중 쓸 만한 것(_usable)은 보통 4분의 3, 그중 그 칸으로 분류되는 것은
# 다시 일부라, 100건짜리 니치는 20줄을 만들지 못한다.
THIN_TOTAL = 100


def _fill_notes(per_cat, evidence, want, search_spent, pool_size):
    """왜 이 칸이 짧은지 말한다. 짧은 것과 고장난 것은 화면에서 구별되지 않는다."""
    if not per_cat:
        # 한 줄도 못 건졌다. 그건 섹션의 empty_reason 이 할 말이지,
        # "0칸 전부 채웠습니다"라고 적으면 거짓말이 된다.
        return []
    # 분모는 **있는 칸이 아니라 있을 수 있는 칸 전부**다(종류 4 × 부문 27).
    # 한 줄도 없는 칸은 per_cat 에 아예 나타나지 않아서, per_cat 만 세면
    # "0개인 칸"이 분모에서도 조용히 빠진다 — 그러면 다 채운 것처럼 보인다.
    every = [(kind, category) for kind in KINDS for category in CATEGORIES]
    full = [k for k in every if per_cat.get(k, 0) >= want]
    short = [k for k in every if per_cat.get(k, 0) < want]
    if not short:
        return [f"{len(full)}칸 전부 {want}개를 채웠습니다 "
                f"(검색 {search_spent}회, 후보 {pool_size}개)."]

    # 진짜로 얇은 칸 = 겨냥해 물어봤는데 GitHub 자신이 몇 건 없다고 답한 칸.
    scarce = sorted((evidence[k], k) for k in short
                    if k in evidence and evidence[k] < THIN_TOTAL)
    named = ", ".join(f"{kind}/{cat} {total}건"
                      for total, (kind, cat) in scarce[:8])
    out = [f"{len(full)}/{len(every)}칸(종류 {len(KINDS)} × 부문 {len(CATEGORIES)})이 "
           f"{want}개를 채웠습니다 (검색 {search_spent}회, 후보 {pool_size}개)."]
    if scarce:
        out.append(
            f"짧은 칸 {len(short)}곳 중 {len(scarce)}곳은 GitHub 검색 자체에 "
            f"후보가 {THIN_TOTAL}건 미만인 니치입니다 — {named}"
            f"{' 외' if len(scarce) > 8 else ''}. 맞지 않는 레포로 채우지 않습니다."
        )
    # 겨냥해 봤는데도 짧은 칸과, 예산이 모자라 아직 손도 못 댄 칸은 다른 이야기다.
    # 한 덩어리로 "못 채웠습니다"라고 적으면 고칠 수 있는 것과 없는 것이 섞인다.
    blocked = [k for k in short if evidence.get(k, 0) >= THIN_TOTAL]
    untried = [k for k in short if k not in evidence]
    if blocked:
        out.append(
            f"{len(blocked)}곳은 검색 후보는 많은데 규칙 분류가 그 부문으로 "
            "보내지 못한 칸입니다. ANTHROPIC_API_KEY 로 부문 분류를 LLM 에 "
            "맡기면 줄어듭니다.")
    if untried:
        out.append(
            f"{len(untried)}곳은 이번 회차 검색 예산({search_spent}회) 안에서 "
            "손대지 못했습니다 — GH_READ_TOKEN 이 있으면 분당 30회가 되어 "
            "한 번에 다 팝니다.")
    return out
