"""web/index.html 과 web/sw.js 검증 — **화면이 실제로 그려지는가**.

`python tests/test_render.py` 로 돌린다. test_pipeline / test_coverage 의 자매 파일이다.

이 파일이 생긴 이유는 하나다. 2026-09-21, 보드가 화면에 아무것도 띄우지 못하고
"보드를 불러오는 중입니다…" 에서 멈췄다. 원인은 커밋 b9b97c2 가 `renderKeywordStrip`
등 **렌더 함수 10개를 통째로 지웠는데** 호출부는 남겨 둔 것이었다. renderBoard 가
첫 줄에서 ReferenceError 로 죽으니 그 뒤가 전부 안 그려졌다.

그때까지의 검사는 전부 파이썬 쪽이었다. 파이프라인 테스트 51개가 다 통과했고
보드 JSON 도 멀쩡했다 — **JSON 이 옳다는 것과 화면이 그려진다는 것은 다른 명제였다.**
그 사이를 아무도 안 보고 있었다. 여기가 그 자리다.

브라우저를 띄우지 않는다. 이 앱은 pip 없이 도는 게 원칙(비개발자가 직접 돌린다)이라
Playwright 같은 의존성을 넣을 수 없다. 대신 `<script>` 블록을 정적으로 읽어
"부르는데 정의가 없는 것"을 찾는다. 위 사고는 정확히 그 모양이었으므로 이걸로 잡힌다.
"""

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

INDEX = os.path.join(ROOT, "web", "index.html")
SW = os.path.join(ROOT, "web", "sw.js")
BOARD = os.path.join(ROOT, "boards", "latest.json")

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    mark = "  ok" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f"  — {detail}" if detail and not cond else ""))


html = io.open(INDEX, encoding="utf-8").read()
sw = io.open(SW, encoding="utf-8").read()
script = html[html.index("<script>"):html.rindex("</script>")]


# ── 1. 부르는데 정의가 없는 함수 ───────────────────────────────────────────
# 실제 사고: `renderKeywordStrip(keywordSection)` 은 남고 정의는 지워졌다.

# 점 뒤에 오는 건 메서드 호출이므로 뺀다 (`arr.map(` 의 map 은 우리 함수가 아니다).
CALLED = set(re.findall(r"(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(", script))

DEFINED = set(re.findall(r"function\s+([A-Za-z_$][\w$]*)", script))
DEFINED |= set(re.findall(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=", script))
# 콜백 인자로 받은 함수도 정의된 것으로 친다: `function regionSplitHTML(cards, renderGroup)`
for args in re.findall(r"function\s+[A-Za-z_$][\w$]*\s*\(([^)]*)\)", script):
    DEFINED |= {a.strip() for a in args.split(",") if a.strip()}

# 자바스크립트/DOM 이 원래 주는 것들. 우리 코드가 정의할 필요가 없다.
GLOBALS = {
    "if", "for", "while", "switch", "catch", "return", "function", "typeof",
    "new", "await", "async", "do", "else", "try", "throw", "of", "in",
    "Number", "String", "Array", "Object", "JSON", "Date", "Math", "Intl",
    "Error", "Boolean", "Promise", "Set", "Map", "RegExp", "parseInt",
    "parseFloat", "isNaN", "isFinite", "encodeURIComponent",
    "decodeURIComponent", "setTimeout", "clearTimeout", "setInterval",
    "requestAnimationFrame", "fetch", "alert", "URL", "Intl",
}

undefined_calls = sorted(CALLED - DEFINED - GLOBALS)
check("index.html: 정의 없이 호출되는 함수가 없다",
      not undefined_calls,
      f"{undefined_calls} — renderBoard 가 ReferenceError 로 죽어 화면이 빈다")


# ── 2. el.* 로 잡는 DOM 이 실제로 문서에 있는가 ────────────────────────────
# el.kwStrip 이 null 이면 innerHTML 대입에서 죽는다. 같은 모양의 사고다.
el_block = re.search(r"const el = \{(.*?)\n  \};", script, re.S)
check("index.html: el 맵을 찾을 수 있다", bool(el_block))
if el_block:
    ids = dict(re.findall(r"(\w+):\s*document\.getElementById\(\"([^\"]+)\"\)", el_block.group(1)))
    doc_ids = set(re.findall(r'id="([^"]+)"', html))
    missing = sorted(k for k, v in ids.items() if v not in doc_ids)
    check("index.html: el 이 가리키는 id 가 문서에 전부 있다",
          not missing, f"{missing} 의 대상 엘리먼트가 마크업에 없다")


# ── 3. 보드 JSON 의 모든 섹션이 그려질 수 있는가 ──────────────────────────
# sectionHTML 은 섹션 id 로 분기하고, 어디에도 안 걸리면 cardHTML 로 떨어진다.
# 그 낙하 지점이 비어 있으면 낯선 섹션 하나가 페이지 전체를 죽인다 (실제로 죽었다).
check("index.html: 낯선 섹션의 낙하 지점(cardHTML/plainCardHTML)이 있다",
      "function cardHTML" in script and "function plainCardHTML" in script,
      "새 섹션이 생기면 그 섹션이 페이지 전체를 죽인다")

if os.path.exists(BOARD):
    board = json.load(io.open(BOARD, encoding="utf-8"))
    section_ids = [s.get("id") for s in board.get("sections", [])]
    check("보드에 섹션이 실려 있다", bool(section_ids), "sections 가 비었다")
    # 카드가 실린 섹션은 반드시 렌더 분기를 타야 한다.
    for s in board.get("sections", []):
        sid = s.get("id")
        if not s.get("cards"):
            continue
        branch = f'"{sid}"' in script or sid == "keywords" or sid == "model_updates"
        check(f"섹션 '{sid}' 을 그릴 분기가 있다", branch,
              "sectionHTML 에 이 섹션 id 분기가 없다")
    # 마일스톤을 싣는 섹션이 있으면 그리는 쪽도 있어야 한다.
    if any(s.get("milestone") for s in board.get("sections", [])):
        check("마일스톤 데이터를 그리는 함수가 있다",
              "function milestoneHTML" in script,
              "데이터는 실려 오는데 화면에는 안 나온다")

# ── 3-b. '왜 이만큼뿐인가'를 말할 자리가 있는가 ───────────────────────────
# 실제 사고: github_skills 는 "부문 N곳이 20개를 못 채웠습니다 …" 라는 설명을
# 만들어 두고 있었는데 board.py 가 섹션별 notes 를 받지 못해 전부 버렸다.
# 사용자에게는 이유 없는 짧은 목록만 보였고, 짧은 것과 고장난 것을 구별하지 못했다.
check("index.html: 섹션 주석(s.notes)을 그리는 자리가 있다",
      "s.notes" in script,
      "설명이 만들어져도 화면에 나올 곳이 없다")
check("index.html: 마일스톤 주석(ms.note)을 그리는 자리가 있다",
      "ms.note" in script,
      "'최근 N건만 실었습니다' 가 화면에 안 나온다")


# ── 4. 서비스 워커가 고친 코드를 기기에 전달할 수 있는가 ───────────────────
# 실제 사고: 셸이 '캐시 우선 + 고정 캐시 이름'이라, 렌더가 깨진 index.html 이
# 캐시에 박힌 뒤로는 고쳐서 배포해도 화면이 영원히 그대로였다.
check("sw.js: 셸을 캐시 우선으로만 내주지 않는다",
      "staleWhileRevalidate" in sw and "cacheFirst" not in sw,
      "셸이 캐시 우선이면 고친 코드가 설치된 앱에 도달하지 못한다")
check("sw.js: 셸이 바뀌면 열린 창에 알린다",
      "shell-updated" in sw and "shell-updated" in script,
      "워커와 페이지 중 한쪽만 신호를 알면 새로고침이 일어나지 않는다")
check("sw.js: latest.json 은 네트워크 우선이다",
      "networkFirst" in sw and "isBoardRequest" in sw,
      "보드 데이터가 캐시에 갇히면 매일 같은 화면을 본다")


print(f"\n{len(PASS)} 통과 / {len(FAIL)} 실패")
if FAIL:
    print("실패:", ", ".join(FAIL))
raise SystemExit(1 if FAIL else 0)
