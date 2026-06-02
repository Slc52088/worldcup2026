/**
 * sw.js — Service Worker
 * 缓存策略：应用外壳(App Shell)预缓存 + 运行时网络优先回退缓存。
 * 注意：API 响应不长期缓存（数据需实时），仅缓存静态框架以支持离线打开。
 */
const CACHE = "wc2026-v1";
const SHELL = [
  "./",
  "./index.html",
  "./style.css",
  "./app.js",
  "./charts.js",
  "./config.js",
  "./manifest.json",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // API 请求：网络优先，不缓存（保证实时性）
  if (url.pathname.startsWith("/api/")) {
    e.respondWith(fetch(e.request).catch(() => new Response(
      JSON.stringify({ detail: "离线状态，无法获取实时数据" }),
      { status: 503, headers: { "Content-Type": "application/json" } }
    )));
    return;
  }
  // 静态资源：缓存优先，回退网络
  e.respondWith(
    caches.match(e.request).then((cached) =>
      cached || fetch(e.request).then((resp) => {
        if (resp.ok && e.request.method === "GET") {
          const clone = resp.clone();
          caches.open(CACHE).then((c) => c.put(e.request, clone));
        }
        return resp;
      }).catch(() => caches.match("./index.html"))
    )
  );
});
