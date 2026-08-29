const STATE_LABELS = {
  routing: "routing",
  thinking: "thinking",
  tool: "werkzeug",
  done: "fertig",
  error: "fehler",
  awaiting_confirm: "bestätigung",
  listening: "listening",
  transcribing: "transcribing",
  speaking: "speaking",
  bereit: "bereit",
};

const els = {
  chassis: document.getElementById("chassis"),
  meta: document.getElementById("meta"),
  model: document.getElementById("model"),
  elapsed: document.getElementById("elapsed"),
  led: document.getElementById("led"),
  link: document.getElementById("link"),
  state: document.getElementById("state"),
  wave: document.getElementById("wave"),
  turn: document.getElementById("turn"),
  query: document.getElementById("query"),
  rail: document.getElementById("rail"),
  slip: document.getElementById("slip"),
  answer: document.getElementById("answer"),
  fault: document.getElementById("fault"),
  idle: document.getElementById("idle"),
  form: document.getElementById("form"),
  input: document.getElementById("input"),
  send: document.getElementById("send"),
  cancel: document.getElementById("cancel"),
  attach: document.getElementById("attach"),
  ptt: document.getElementById("ptt"),
  confirm: document.getElementById("confirm"),
  confirmDetail: document.getElementById("confirm-detail"),
  approve: document.getElementById("approve"),
  deny: document.getElementById("deny"),
};

const state = {
  ws: null,
  connected: false,
  requestId: null,
  busy: false,
  backoff: 500,
  daemonOrigin: "",
  source: "hud",
  attachments: [],
  context: {},
  timer: null,
  startedAt: 0,
  lastTool: null,
  media: null,
  chunks: [],
  recording: false,
};

function isTauri() {
  return Boolean(window.__TAURI_INTERNALS__ || window.__TAURI__);
}

function uuid() {
  return crypto.randomUUID();
}

function daemonUrl(path) {
  const origin = state.daemonOrigin || (isTauri() ? "http://127.0.0.1:8765" : location.origin);
  return `${origin}${path}`;
}

function wsUrl() {
  const origin = state.daemonOrigin || (isTauri() ? "http://127.0.0.1:8765" : location.origin);
  const url = new URL(origin);
  const proto = url.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${url.host}/ws`;
}

function friendlyError(raw) {
  const text = String(raw || "");
  if (/internal s|not valid json|unexpected token/i.test(text)) {
    return "Das Modell hat nicht geantwortet. Ollama prüfen, dann nochmal senden.";
  }
  return text || "Fehler";
}

function setModel(name) {
  if (!name) {
    els.model.hidden = true;
    els.model.textContent = "";
    return;
  }
  els.model.hidden = false;
  els.model.textContent = name;
}

function setLink(online) {
  state.connected = online;
  els.led.dataset.state = online ? "online" : "offline";
  els.link.textContent = online ? "verbunden" : "getrennt";
}

function setPhase(phase, detail) {
  els.state.textContent = STATE_LABELS[phase] ?? phase;
  const listening = phase === "listening" || phase === "transcribing" || phase === "speaking";
  els.wave.hidden = !listening;
}

function resizeInput() {
  els.input.style.height = "auto";
  els.input.style.height = `${Math.min(els.input.scrollHeight, 160)}px`;
}

function beginTurn(text) {
  els.idle.hidden = true;
  els.turn.hidden = false;
  els.query.textContent = text;
  els.rail.replaceChildren();
  els.slip.hidden = true;
  els.answer.textContent = "";
  els.fault.hidden = true;
  els.fault.textContent = "";
  state.lastTool = null;
}

function addTool(name, args) {
  const item = document.createElement("li");
  item.className = "stamp";
  const head = document.createElement("div");
  head.className = "stamp-head";
  const label = document.createElement("span");
  label.className = "stamp-name";
  label.textContent = name;
  const detail = document.createElement("span");
  detail.className = "stamp-args";
  detail.textContent = JSON.stringify(args ?? {});
  head.append(label, detail);
  const result = document.createElement("p");
  result.className = "stamp-result";
  result.hidden = true;
  item.append(head, result);
  els.rail.append(item);
  state.lastTool = { item, result, name };
}

function finishTool(name, text) {
  if (!state.lastTool || state.lastTool.name !== name) {
    addTool(name, {});
  }
  if (state.lastTool) {
    state.lastTool.result.hidden = false;
    state.lastTool.result.textContent = text;
  }
}

function appendAnswer(text) {
  els.slip.hidden = false;
  els.answer.textContent += text;
}

function setBusy(busy) {
  state.busy = busy;
  els.chassis.classList.toggle("is-busy", busy);
  els.send.disabled = busy || !state.connected;
  els.cancel.hidden = !busy;
  els.input.readOnly = busy;
  if (busy) {
    state.startedAt = Date.now();
    els.elapsed.hidden = false;
    if (state.timer) {
      window.clearInterval(state.timer);
    }
    state.timer = window.setInterval(() => {
      els.elapsed.textContent = `${((Date.now() - state.startedAt) / 1000).toFixed(1)}s`;
    }, 100);
  } else if (state.timer) {
    window.clearInterval(state.timer);
    state.timer = null;
  }
}

function sendJson(payload) {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    return false;
  }
  state.ws.send(JSON.stringify(payload));
  return true;
}

async function loadStatus() {
  try {
    const res = await fetch(daemonUrl("/api/status"));
    if (!res.ok) {
      return;
    }
    const data = await res.json();
    const host = `${data.host}:${data.port}`;
    const vault = data.vault ?? "kein Vault";
    els.meta.textContent = `${host} · ${vault}`;
  } catch {
    /* Daemon-Status ist optional */
  }
}

async function playTts(text) {
  if (!text) {
    return;
  }
  setPhase("speaking");
  try {
    const res = await fetch(daemonUrl("/api/tts"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) {
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    await audio.play();
    audio.addEventListener("ended", () => URL.revokeObjectURL(url), { once: true });
  } catch {
    /* TTS ist optional */
  }
}

function handleMessage(msg) {
  if (msg.id && state.requestId && msg.id !== state.requestId) {
    return;
  }

  switch (msg.type) {
    case "status":
      setPhase(msg.state, msg.detail);
      if (msg.model) {
        setModel(msg.model);
      }
      break;
    case "tool_call":
      setPhase("tool");
      addTool(msg.name, msg.args);
      break;
    case "tool_result":
      finishTool(msg.name, msg.text ?? "");
      break;
    case "token":
      appendAnswer(msg.text ?? "");
      break;
    case "result":
      if (msg.text && els.answer.textContent !== msg.text) {
        els.slip.hidden = false;
        els.answer.textContent = msg.text;
      }
      setPhase("done");
      setBusy(false);
      if (state.source === "voice") {
        playTts(msg.text || els.answer.textContent);
      }
      state.requestId = null;
      state.source = "hud";
      break;
    case "confirm_req":
      setPhase("awaiting_confirm");
      els.confirmDetail.textContent = msg.detail || msg.action || "";
      els.confirm.showModal();
      break;
    case "error":
      els.fault.hidden = false;
      els.fault.textContent = friendlyError(msg.message);
      setPhase("error");
      setBusy(false);
      break;
    default:
      break;
  }
}

function connect() {
  const ws = new WebSocket(wsUrl());
  state.ws = ws;

  ws.addEventListener("open", () => {
    state.backoff = 500;
    setLink(true);
    setBusy(state.busy);
    loadStatus();
    if (!state.busy) {
      setPhase("bereit");
    }
  });

  ws.addEventListener("message", (event) => {
    try {
      handleMessage(JSON.parse(event.data));
    } catch {
      els.fault.hidden = false;
      els.fault.textContent = "Ungültige Nachricht vom Daemon.";
    }
  });

  ws.addEventListener("close", () => {
    setLink(false);
    els.send.disabled = true;
    if (!state.busy) {
      setPhase("bereit");
    }
    window.setTimeout(connect, state.backoff);
    state.backoff = Math.min(state.backoff * 2, 5000);
  });
}

function submitRequest(text, source = "hud") {
  const requestId = uuid();
  state.requestId = requestId;
  state.source = source;
  beginTurn(text);
  setPhase("routing");
  setBusy(true);
  const ok = sendJson({
    type: "request",
    id: requestId,
    source,
    text,
    attachments: state.attachments,
    context: state.context,
  });
  state.attachments = [];
  if (!ok) {
    els.fault.hidden = false;
    els.fault.textContent = "Keine Verbindung zum Daemon.";
    setPhase("error");
    setBusy(false);
    state.requestId = null;
  }
}

els.form.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = els.input.value.trim();
  if (!text || state.busy) {
    return;
  }
  els.input.value = "";
  resizeInput();
  submitRequest(text, "hud");
});

els.input.addEventListener("input", resizeInput);

els.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    els.form.requestSubmit();
  }
});

els.cancel.addEventListener("click", () => {
  if (!state.requestId) {
    return;
  }
  sendJson({ type: "cancel", id: state.requestId });
});

function resolveConfirm(approved) {
  if (state.requestId) {
    sendJson({ type: "confirm", id: state.requestId, approved });
  }
  els.confirm.close();
}

els.approve.addEventListener("click", () => resolveConfirm(true));
els.deny.addEventListener("click", () => resolveConfirm(false));

async function attachScreen() {
  try {
    if (isTauri() && window.__TAURI__?.core?.invoke) {
      const path = await window.__TAURI__.core.invoke("capture_front_window");
      state.context = { ...state.context, screenshot: path, active_app: "frontmost" };
      state.attachments = [{ type: "image", path }];
      els.attach.classList.add("is-hot");
      return;
    }
    const res = await fetch(daemonUrl("/api/capture"), { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Capture fehlgeschlagen");
    }
    state.context = { ...state.context, screenshot: data.path };
    state.attachments = [{ type: "image", path: data.path }];
    els.attach.classList.add("is-hot");
  } catch (err) {
    els.fault.hidden = false;
    els.turn.hidden = false;
    els.idle.hidden = true;
    els.fault.textContent = err.message || "Fenster konnte nicht erfasst werden.";
  }
}

els.attach.addEventListener("click", () => {
  attachScreen();
});

async function transcribeBlob(blob) {
  const body = new FormData();
  body.append("file", blob, "speech.webm");
  const res = await fetch(daemonUrl("/api/transcribe"), { method: "POST", body });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Transkription fehlgeschlagen");
  }
  return data.text;
}

async function startPtt() {
  if (state.recording || state.busy) {
    return;
  }
  state.chunks = [];
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const media = new MediaRecorder(stream);
    state.media = media;
    media.addEventListener("dataavailable", (event) => {
      if (event.data.size) {
        state.chunks.push(event.data);
      }
    });
    media.start();
    state.recording = true;
    els.ptt.classList.add("is-hot");
    setPhase("listening");
    els.wave.hidden = false;
  } catch (err) {
    els.fault.hidden = false;
    els.turn.hidden = false;
    els.idle.hidden = true;
    els.fault.textContent = err.message || "Mikrofon nicht verfügbar.";
  }
}

async function stopPtt() {
  if (!state.recording || !state.media) {
    return;
  }
  const media = state.media;
  const stream = media.stream;
  const blob = await new Promise((resolve) => {
    media.addEventListener(
      "stop",
      () => resolve(new Blob(state.chunks, { type: media.mimeType || "audio/webm" })),
      { once: true },
    );
    media.stop();
  });
  stream.getTracks().forEach((track) => track.stop());
  state.media = null;
  state.recording = false;
  els.ptt.classList.remove("is-hot");
  setPhase("transcribing");
  try {
    const text = (await transcribeBlob(blob)).trim();
    if (!text) {
      setPhase("bereit");
      els.wave.hidden = true;
      return;
    }
    els.input.value = "";
    submitRequest(text, "voice");
  } catch (err) {
    setPhase("error");
    els.wave.hidden = true;
    els.fault.hidden = false;
    els.turn.hidden = false;
    els.idle.hidden = true;
    els.fault.textContent = err.message || "Sprache nicht erkannt.";
  }
}

els.ptt.addEventListener("mousedown", (event) => {
  event.preventDefault();
  startPtt();
});
els.ptt.addEventListener("mouseup", () => stopPtt());
els.ptt.addEventListener("mouseleave", () => {
  if (state.recording) {
    stopPtt();
  }
});
els.ptt.addEventListener("touchstart", (event) => {
  event.preventDefault();
  startPtt();
});
els.ptt.addEventListener("touchend", (event) => {
  event.preventDefault();
  stopPtt();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    if (els.confirm.open) {
      event.preventDefault();
      resolveConfirm(false);
      return;
    }
    if (isTauri() && window.__TAURI__?.core?.invoke) {
      window.__TAURI__.core.invoke("hide_hud");
      return;
    }
    els.input.value = "";
    resizeInput();
    els.input.focus();
    return;
  }
  if ((event.ctrlKey || event.metaKey) && event.code === "Space" && !event.repeat) {
    event.preventDefault();
    startPtt();
  }
});

document.addEventListener("keyup", (event) => {
  if ((event.ctrlKey || event.code === "Space") && state.recording) {
    if (event.code === "Space") {
      event.preventDefault();
      stopPtt();
    }
  }
});

async function boot() {
  if (isTauri()) {
    document.body.classList.add("is-tauri");
    try {
      const origin = await window.__TAURI__.core.invoke("daemon_url");
      if (origin) {
        state.daemonOrigin = origin;
      }
    } catch {
      state.daemonOrigin = "http://127.0.0.1:8765";
    }
    try {
      const listen = window.__TAURI__?.event?.listen;
      if (listen) {
        await listen("ptt-start", () => startPtt());
        await listen("ptt-stop", () => stopPtt());
        await listen("attach-screen", () => attachScreen());
        await listen("focus-input", () => els.input.focus());
      }
    } catch {
      /* Events sind optional */
    }
  }
  setBusy(false);
  connect();
  els.input.focus();
}

boot();
