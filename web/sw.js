// AI Alert — 서비스 워커
//
// 셸(index.html·매니페스트)은 **stale-while-revalidate**, latest.json 은 네트워크 우선.
//
// 예전에는 셸이 '캐시 우선 + 고정 캐시 이름'이었다. 그 조합은 한 번 설치되면
// 고친 코드가 기기에 영원히 도달하지 않는다 — 실제로 렌더가 깨진 셸이 캐시에
// 박혀서, 파일을 고쳐 배포해도 화면은 계속 "보드를 불러오는 중입니다…" 였다.
// 캐시 이름을 손으로 올리는 규칙은 사람이 잊는다(잊었다). 그래서 규칙 대신
// 구조로 막는다: 캐시에서 즉시 내주되 **매번 뒤에서 새로 받아 캐시를 덮고**,
// 내용이 달라졌으면 페이지에 알려 한 번 새로고침하게 한다.
const CACHE_NAME = "ai-alert-shell-v2";
const SHELL_URLS = ["./", "./index.html", "./manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) =>
        // addAll은 하나라도 실패하면 전체가 실패한다. 서버가 "./"에 디렉터리
        // 목록을 내려주지 않는 배포 환경도 있으니, 개별로 넣고 실패는 무시한다.
        Promise.all(SHELL_URLS.map((url) => cache.add(url).catch(() => {})))
      )
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
      )
      .then(() => self.clients.claim())
  );
});

function isBoardRequest(url) {
  return url.pathname.endsWith("latest.json");
}

async function networkFirst(request) {
  try {
    const fresh = await fetch(request, { cache: "no-store" });
    if (fresh && fresh.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, fresh.clone());
    }
    return fresh;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) return cached;
    throw err;
  }
}

async function notifyShellUpdated() {
  const clients = await self.clients.matchAll({ type: "window" });
  clients.forEach((client) => client.postMessage({ type: "shell-updated" }));
}

// 캐시본을 곧바로 내주고(앱이 즉시 뜬다), 같은 요청을 뒤에서 한 번 더 받아
// 캐시를 덮는다. 바뀌었으면 열려 있는 창에 알린다.
async function staleWhileRevalidate(request) {
  const cached = await caches.match(request);

  const update = (async () => {
    let fresh;
    try {
      fresh = await fetch(request, { cache: "no-store" });
    } catch (err) {
      return null;
    }
    if (!fresh || !fresh.ok) return null;
    const cache = await caches.open(CACHE_NAME);
    // 바뀌었는지 보려면 본문을 읽어야 하는데, 읽은 응답은 다시 못 쓴다.
    // 그래서 캐시에 넣을 사본과 비교용 사본을 따로 둔다.
    const forCache = fresh.clone();
    if (cached) {
      const [oldText, newText] = await Promise.all([cached.clone().text(), fresh.clone().text()]);
      await cache.put(request, forCache);
      if (oldText !== newText) await notifyShellUpdated();
    } else {
      await cache.put(request, forCache);
    }
    return fresh;
  })();

  if (cached) {
    // 갱신은 응답을 붙잡아 두지 않는다 — 앱은 캐시본으로 이미 떠 있다.
    self.registration && update;
    return cached;
  }
  const fresh = await update;
  if (fresh) return fresh;
  const fallback = await caches.match("./index.html");
  if (fallback) return fallback;
  return fetch(request);
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (isBoardRequest(url)) {
    event.respondWith(networkFirst(request));
    return;
  }

  const isShell =
    request.mode === "navigate" ||
    SHELL_URLS.some((shell) => new URL(shell, self.registration.scope).href === request.url);

  if (isShell) {
    event.respondWith(staleWhileRevalidate(request));
  }
});
