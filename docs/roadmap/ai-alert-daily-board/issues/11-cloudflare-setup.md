# 11. 외부 서비스 준비 (Cloudflare + GitHub + Anthropic 키)

Type: task
Status: open
Blocked by: (없음)

## Question

[08](08-runtime-infrastructure.md)에서 **비공개 리포 + Cloudflare Pages** 구조로 정했다.
GitHub Actions가 만든 보드를 Cloudflare에 올리려면 계정과 토큰이 필요한데, 에이전트가 대신 못 한다.

1. `dash.cloudflare.com` 가입 (이메일만으로 가능한지 확인)
2. **Pages 프로젝트 생성** — 이름은 `ai-alert` 정도. 저장소 연결 없이 직접 업로드 방식으로 만든다
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

예상 비용은 **월 약 ₩2,650** (Sonnet 5, 하루 40장 요약 + 섹션 브리핑 기준).
NCP 때와 달리 여기는 **콘솔에서 하드 상한을 걸 수 있다** — 그게 이 키가 상대적으로 안전한 이유다.

## 해결 조건

- [ ] Cloudflare 가입이 카드를 요구하는지 확인: ______
- [ ] Pages 프로젝트 생성됨
- [ ] `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`가 GitHub Actions 시크릿에 등록됨
- [ ] `GH_READ_TOKEN` (공개 저장소 읽기 전용) 발급 후 Actions 시크릿에 등록
- [ ] `ANTHROPIC_API_KEY` 발급 + 월 사용 한도 설정 + Actions 시크릿 등록

## Answer

(미해결)
