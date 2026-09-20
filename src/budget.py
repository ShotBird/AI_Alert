"""하루 호출 예산. 무료 구간을 넘지 않는 책임은 우리 코드에 있다.

NCP에 결제수단이 등록돼 있고 종량제다. 클라우드 콘솔은 알림만 주고 차단은 해주지 않는다.
그래서 여기서 막는다. 규칙은 지도의 Notes에 있고 요지는 둘이다.

1. 상한은 무료 구간의 2% 이하로 잡는다.
2. **카운터를 읽지 못하면 호출하지 않는다** (fail-closed).
   안전장치가 고장났을 때 뚫리는 게 아니라 멈추는 쪽이어야 한다.
"""

import json
import os
from datetime import date

# 무료 구간 대비 한참 아래로 잡는다. 버그가 나도 여기서 멈춘다.
LIMITS = {
    "naver_search": 300,    # 무료 일 25,000
    "naver_trend": 20,      # 무료 월 30,000
    "kakao_search": 300,
    # GitHub 은 **돈이 들지 않는다.** 여기 상한은 비용 통제가 아니라
    # 하루에 어처구니없이 많이 부르는 사고를 막는 용도다. GitHub 자신의
    # 레이트리밋(무인증 core 60/시, search 10/분)이 실제 제약이고 그건 코드가 존중한다.
    # 개발 중 재실행이 잦아 30 이 금방 소진되면서 섹션이 통째로 비는 일이 있었다.
    "github_core": 1200,
    # 200 → 600. 칸(종류×부문) 108개를 20줄씩 채우려면 토픽 훑기 28회로는 어림도
    # 없다. 겨냥 검색이 한 번에 한 칸을 채우므로 한 번 돌 때 170회쯤 쓴다
    # (토픽 28 + 칸 채우기 140). 하루 재실행 서너 번을 감당할 자리를 둔다.
    # GitHub search 는 **일일 한도가 없다** — 분당 10회(무인증)가 전부이고
    # 그건 _Pacer 가 지킨다. 여기 숫자는 폭주 사고를 막는 용도지 비용 통제가 아니다.
    "github_search": 600,
    "anthropic": 60,        # 요약 호출
    "tranco": 40,
    "discord": 60,
    "benchmarks": 20,       # EpochAI · LMArena. CC BY 4.0, 인증 없음          # 초대 링크 조회. 무료이고 인증도 없다           # 도메인 순위. 공짜지만 연속 호출에 429 를 준다
}


class BudgetExceeded(Exception):
    """상한에 닿았다. 오류가 아니라 '이 소스는 오늘 끝'이라는 뜻이다."""


class BudgetUnavailable(Exception):
    """카운터를 읽지도 쓰지도 못한다. 이 경우 호출을 아예 하지 않는다."""


class Budget:
    def __init__(self, path):
        self.path = path
        self.today = date.today().isoformat()
        self.counts = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, encoding="utf-8") as fh:
                    data = json.load(fh)
                if data.get("date") == self.today:
                    self.counts = dict(data.get("counts") or {})
                # 날짜가 다르면 새 날이므로 0에서 시작한다.
            else:
                # 파일이 없는 것은 정상이다 (첫 실행). 디렉터리에 쓸 수 있는지만 확인한다.
                parent = os.path.dirname(self.path) or "."
                os.makedirs(parent, exist_ok=True)
                if not os.access(parent, os.W_OK):
                    raise OSError("counter directory is not writable")
        except Exception as exc:
            # 읽을 수 없으면 "0회 썼다"고 가정하지 않는다. 그게 fail-open이다.
            raise BudgetUnavailable(f"호출 카운터를 사용할 수 없습니다: {exc}") from exc

    def check(self, key, n=1):
        """호출 전에 부른다. 상한을 넘으면 BudgetExceeded."""
        limit = LIMITS.get(key)
        if limit is None:
            raise BudgetUnavailable(f"예산이 정의되지 않은 키입니다: {key}")
        used = self.counts.get(key, 0)
        if used + n > limit:
            raise BudgetExceeded(f"{key}: {used}/{limit} 도달")
        return limit - used

    def spend(self, key, n=1):
        self.counts[key] = self.counts.get(key, 0) + n

    def report(self):
        """메일 한 줄에 넣을 사용량. 숫자가 이상하면 바로 눈에 띈다."""
        return {k: f"{self.counts.get(k, 0)}/{v}" for k, v in LIMITS.items()
                if self.counts.get(k)}

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"date": self.today, "counts": self.counts},
                      fh, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)
