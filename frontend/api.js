// api.js — REST + WebSocket client for the hPersist backend.
// Loaded BEFORE the React shell. Exposes window.api and window.HP.

(function () {
  const BASE = "/api/v1";

  async function request(method, path, body, opts) {
    opts = opts || {};
    const init = {
      method,
      headers: { "Accept": "application/json" },
    };
    if (body !== undefined && !(body instanceof FormData)) {
      init.headers["Content-Type"] = "application/json";
      init.body = typeof body === "string" ? body : JSON.stringify(body);
    } else if (body instanceof FormData) {
      init.body = body;
    }
    const url = path.startsWith("http") ? path : BASE + path;
    const res = await fetch(url, init);
    if (opts.raw) return res;
    if (res.status === 204) return null;
    const ct = res.headers.get("content-type") || "";
    const data = ct.includes("application/json") ? await res.json() : await res.text();
    if (!res.ok) {
      const err = new Error((data && data.detail) || res.statusText || ("HTTP " + res.status));
      err.status = res.status;
      err.body = data;
      throw err;
    }
    return data;
  }

  const api = {
    get:    (p, opts) => request("GET", p, undefined, opts),
    post:   (p, b, opts) => request("POST", p, b, opts),
    del:    (p, opts) => request("DELETE", p, undefined, opts),
    raw:    (p, opts) => request("GET", p, undefined, Object.assign({ raw: true }, opts || {})),

    // sugar
    inventories:        () => api.get("/inventories"),
    inventory:          (id) => api.get("/inventories/" + id),
    inventoryServers:   (id) => api.get("/inventories/" + id + "/servers"),
    inventoryParts:     (id) => api.get("/inventories/" + id + "/parts"),
    inventoryHealth:    (id) => api.get("/inventories/" + id + "/health"),
    inventoryLogs:      (id) => api.get("/inventories/" + id + "/logs"),
    deleteInventory:    (id) => api.del("/inventories/" + id),
    server:             (id) => api.get("/servers/" + id),
    serverRaw:          (id) => api.get("/servers/" + id + "/raw"),
    startCollection:    (body) => api.post("/collections", body),
    validateCsv:        (text) => api.post("/collections/validate-csv", { text: text }),
    networkPreview:     (cidr) => api.get("/network/preview?cidr=" + encodeURIComponent(cidr)),
    networkScan:        (cidr, opts) => {
      const q = new URLSearchParams({ cidr });
      if (opts) for (const k of Object.keys(opts)) q.set(k, opts[k]);
      return new EventSource(BASE + "/network/scan?" + q.toString());
    },
    smartHandsGenerate: (body) => api.post("/smart-hands/generate", body),
    smartHandsProcess:  (file) => {
      const fd = new FormData();
      fd.append("file", file);
      return api.post("/smart-hands/process", fd);
    },
    redfishTest:        (body) => api.post("/tools/redfish-test", body),
    redfishHistory:     () => api.get("/tools/redfish-test/history"),
    redfishEndpoints:   () => api.get("/tools/redfish-test/endpoints"),
    partsurferSearch:   (q, refresh) => api.get("/tools/partsurfer/search?q=" + encodeURIComponent(q) + (refresh ? "&refresh=true" : "")),
    bomCompare:         (a, b) => api.get("/tools/bom-compare?a=" + encodeURIComponent(a) + "&b=" + encodeURIComponent(b)),
    fleet:              () => api.get("/stats/fleet"),
    rollup:             (days) => api.get("/stats/rollup?window_days=" + (days || 30)),
    statsExportUrl:     (days) => BASE + "/stats/export?window_days=" + (days || 30),
    locales:            () => api.get("/locales"),
    locale:             (code) => api.get("/locales/" + code),
    getSettings:        () => api.get("/settings"),
    patchSettings:      (body) => request("PATCH", "/settings", body),
    insightRun:         (body) => api.post("/insight/run", body),
    insightTest:        () => api.post("/insight/test"),
    insightTemplates:   () => api.get("/insight/report-templates"),
    insightRunStream:   async function* (body) {
      // Async iterator over SSE events from /insight/run/stream.
      // Yields: {event:"reasoning_delta"|"content_delta", data:{text}} | {event:"done", data:{...}} | {event:"error", data:{detail}}
      const res = await fetch(BASE + "/insight/run/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "text/event-stream" },
        body: JSON.stringify(body),
      });
      if (!res.ok && res.status !== 200) {
        let detail = res.statusText;
        try { const j = await res.json(); detail = j.detail || detail; } catch {}
        throw new Error(detail);
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        // Split on blank-line separator (SSE event delimiter).
        let idx;
        while ((idx = buf.indexOf("\n\n")) >= 0) {
          const raw = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          let evt = "message"; let data = "";
          for (const line of raw.split("\n")) {
            if (line.startsWith("event:")) evt = line.slice(6).trim();
            else if (line.startsWith("data:")) data += line.slice(5).trim();
          }
          if (!data) continue;
          try { yield { event: evt, data: JSON.parse(data) }; } catch {}
        }
      }
    },
    exportBlob:         async (body) => {
      const res = await fetch(BASE + "/exports", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("export failed: " + res.status);
      return { blob: await res.blob(), filename: (res.headers.get("content-disposition") || "").split("filename=")[1]?.replace(/"/g, "") || "export" };
    },
    jobSocket:          (inventory_id, onMessage, onClose) => {
      const proto = location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(proto + "//" + location.host + "/ws/jobs/" + inventory_id);
      ws.onmessage = (e) => { try { onMessage(JSON.parse(e.data)); } catch {} };
      ws.onclose = () => onClose && onClose();
      return ws;
    },
  };

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  }

  // ── i18n ──
  const i18n = {
    pack: { app: {}, nav: {}, common: {} },
    code: "en",
    t(key, vars) {
      const parts = key.split(".");
      let v = i18n.pack;
      for (const p of parts) v = (v && v[p]) || null;
      if (typeof v !== "string") return key;
      if (vars) for (const k of Object.keys(vars)) v = v.replace("{" + k + "}", vars[k]);
      return v;
    },
    async load(code) {
      try {
        i18n.pack = await api.locale(code);
        i18n.code = code;
        document.documentElement.lang = code;
      } catch {}
    },
  };

  // Compatibility shim so shell.jsx (which reads counts.inventories from window.HP)
  // can boot before the API responds. The counts get refreshed on every screen.
  window.HP = window.HP || { INVENTORIES: [], SERVERS: [] };

  window.api = api;
  window.t = i18n.t;
  window.i18n = i18n;
  window.downloadBlob = downloadBlob;

  // Kick off locale load. Default English is bundled so we always have strings.
  i18n.load("en");
})();
