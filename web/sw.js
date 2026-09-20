// AI Alert — 서비스 워커
// 셸(마크업 골격)은 캐시 우선, latest.json 은 네트워크 우선 + 캐시 대체.
// 셸이 바뀌면 CACHE_NAME 을 올려서 activate 단계에서 옛 캐시를 지운다.
const CACHE_NAME = "ai-alert-shell-v1";
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
  return url.pathname.endsWith("/latest.json") || url.pathname.endsWith("latest.json");
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

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const fresh = await fetch(request);
    if (fresh && fresh.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, fresh.clone());
    }
    return fresh;
  } catch (err) {
    // 오프라인 첫 방문(셸이 아직 캐시되지 않음)이면 캐시된 index.html로라도 대체한다.
    const fallback = await caches.match("./index.html");
    if (fallback) return fallback;
    throw err;
  }
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

  if (request.mode === "navigate" || SHELL_URLS.some((shell) => new URL(shell, self.registration.scope).href === request.url)) {
    event.respondWith(cacheFirst(request));
  }
});
