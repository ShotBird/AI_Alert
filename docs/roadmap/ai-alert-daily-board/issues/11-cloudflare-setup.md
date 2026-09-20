# 11. 외부 서비스 준비 (Cloudflare + GitHub + Anthropic 키)

Type: task
Status: in-progress
Blocked by: (없음)

## Question

[08](08-runtime-infrastructure.md)에서 **비공개 리포 + Cloudflare Pages** 구조로 정했다.
GitHub Actions가 만든 보드를 Cloudflare에 올리려면 계정과 토큰이 필요한데, 에이전트가 대신 못 한다.

1. `dash.cloudflare.com` 가입 (이메일만으로 가능한지 확인)
2. **Pages 프로젝트 생성** — 이름은 반드시 `ai-alert-board` (CI 가 이 이름으로 배포한다). 저장소 연결 없이 직접 업로드 방식으로 만든다
3. **API 토큰 발급** — 계정 > API 토큰 > 템플릿에서 `Edit Cloudflare Workers` 또는
   Pages 편집 권한이 있는 커스텀 토큰. 필요한 최소 권한만 준다
4. 토큰과 계정 ID를 **GitHub 리포의 Actions 시크릿**에 넣는다 (`.env`가 아니라 GitHub 쪽이다.
   Actions가 쓰는 값이라 로컬 파일에 둘 이유가 없다)

⚠️ **확인해서 알려줄 것: Cloudflare 가입이 결제수단을 요구하는가?**
요구한다면 여기서 멈추고 보고할 것. 08의 판단(비용 0원)이 무너지면 공개 리포 안을 다시 꺼내 비교해야 한다.
무료 플랜은 카드 없이 쓸 수 있는 것으로 알려져 있으나 직접 확인이 필요하다.

## GitHub 개인 토큰 (PAT)

[10](10-github-trending-signal.md)에서 스타 히스토리를 하루 300회 호출하기로 했다.
무인증은 시간당 60회뿐이라 토큰이 필요하다. **무료이고 공개 저장소 읽기 권한만 있으면 된다.**

1. GitHub > Settings > Developer settings > Personal access tokens > **Fine-grained tokens**
2. 권한은 **Public repositories (read-only)** 만. 다른 건 주지 않는다
3. 만료일은 1년으로 두고 달력에 적어둔다 (만료되면 GitHub 섹션이 조용히 빈다)
4. 발급된 값을 **GitHub Actions 시크릿**에 `GH_READ_TOKEN`으로 등록

## Anthropic API 키 — 이게 있어야 앱의 절반이 켜진다

지금 비어 있는 것이 전부 이 키 하나에 걸려 있다.

| 없을 때 | 있을 때 |
|---|---|
| 카드에 제목만 | 제목 + **한국어 한 줄 요약** |
| 섹션 브리핑 없음 | 섹션마다 **3줄 브리핑** (이것만 읽고 덮어도 되는 것) |
| 키워드가 빈도 기반 임시값 ("에이전트", "오픈") | 표기가 다른 같은 주제를 묶고 **한국어 이름**을 붙임 |

1. `console.anthropic.com` 가입 → **API keys** → 새 키 발급
2. 결제수단 등록이 필요하다. **사용 한도(spend limit)를 월 $5 정도로 걸어두면** 그 이상 청구되지 않는다
3. 발급한 값을 **GitHub Actions 시크릿**에 `ANTHROPIC_API_KEY` 로 등록
4. 로컬에서도 시험하려면 `.env` 에도 같은 줄을 넣는다

예상 비용은 **월 약 ₩5,000** (Sonnet 5). 처음 잡은 ₩2,650 은 요약+브리핑만 있을 때 값이고,
지금은 뉴스 번역·스킬 해설·부문 분류·키워드까지 네 가지가 더 붙어 하루 호출이 ~9건이다
(예산 상한 60건/일 안쪽). 카드 수가 늘어도 이 네 건은 하루 4건으로 고정이다.
NCP 때와 달리 여기는 **콘솔에서 하드 상한을 걸 수 있다** — 그게 이 키가 상대적으로 안전한 이유다.

## 해결 조건

- [x] Cloudflare 가입 완료 (2026-09-21, 사용자 보고). 카드 요구 여부는 사용자가 진행 중 막히지
      않았으므로 무료 플랜은 카드 없이 통과한 것으로 본다 — 결제 화면을 봤다면 정정할 것.
- [ ] Pages 프로젝트 생성됨 (`ai-alert-board`, 저장소 연결 없이 '직접 업로드')
- [ ] `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`가 GitHub Actions 시크릿에 등록됨
- [ ] `GH_READ_TOKEN` (공개 저장소 읽기 전용) 발급 후 Actions 시크릿에 등록
- [ ] `ANTHROPIC_API_KEY` 발급 + 월 사용 한도 설정 + Actions 시크릿 등록

## 지금 남은 것 — 사용자가 할 일

가입은 끝났다. 순서대로 세 가지만 하면 CI 가 매일 아침 알아서 올린다.

**A. Cloudflare Pages 프로젝트**
1. `dash.cloudflare.com` → 왼쪽 **Compute (Workers & Pages)** → **Create** → **Pages** 탭
2. **Upload assets** (저장소 연결 아님) → 프로젝트 이름 **`ai-alert-board`** → Create  ← 철자까지 이대로
3. 첫 업로드를 요구하면 아무 파일이나 하나 올려서 프로젝트만 만들어 둔다. 이후는 CI 가 덮는다

**B. 토큰 두 개**
- Cloudflare: 우상단 계정 → **API 토큰** → **토큰 생성** → 템플릿 `Edit Cloudflare Workers`
  → 생성된 값이 `CLOUDFLARE_API_TOKEN`
- Cloudflare 계정 ID: 대시보드 우측 사이드바 또는 주소창 `dash.cloudflare.com/<여기가 계정ID>`
  → `CLOUDFLARE_ACCOUNT_ID`
- GitHub: Settings → Developer settings → **Fine-grained tokens** → 권한 **Public repositories (read-only)**
  → `GH_READ_TOKEN`
- Anthropic: `console.anthropic.com` → API keys → 새 키. **먼저 Limits 에서 월 $5 상한을 걸고** 발급
  → `ANTHROPIC_API_KEY`

**C. 넣는 곳 — 한 군데뿐이다**
`github.com/hans10102-droid/AI_Alert` → Settings → Secrets and variables → **Actions** → New repository secret.
위 네 개 이름을 그대로 쓴다. **채팅에 붙여넣지 말 것.**

## Answer

(미해결 — 가입만 완료)
