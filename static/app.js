"use strict";

const els = {
  setupForm: document.getElementById("setupForm"),
  outputDir: document.getElementById("outputDir"),
  outputDirError: document.getElementById("outputDirError"),
  pickBtn: document.getElementById("pickBtn"),
  links: document.getElementById("links"),
  linksError: document.getElementById("linksError"),
  itag: document.getElementById("itag"),
  concurrency: document.getElementById("concurrency"),
  limitMode: document.getElementById("limitMode"),
  limitField: document.getElementById("limitField"),
  limitCount: document.getElementById("limitCount"),
  limitError: document.getElementById("limitError"),
  previewBtn: document.getElementById("previewBtn"),
  preview: document.getElementById("preview"),
  previewSummary: document.getElementById("previewSummary"),
  previewList: document.getElementById("previewList"),
  startBtn: document.getElementById("startBtn"),
  cancelBtn: document.getElementById("cancelBtn"),
  status: document.getElementById("status"),
  results: document.getElementById("results"),
  empty: document.getElementById("empty"),
  emptyAction: document.getElementById("emptyAction"),
  queueSummary: document.getElementById("queueSummary"),
};

const linkTpl = document.getElementById("linkTpl");
const fileTpl = document.getElementById("fileTpl");
const previewGroupTpl = document.getElementById("previewGroupTpl");

let cards = {};
let source = null;
let currentJob = "";
let stats = { links: 0, linksDone: 0, total: 0, done: 0 };

/* ------------------------------------------------------------------ */
/* Status + field errors                                              */
/* ------------------------------------------------------------------ */
function setStatus(text, kind) {
  els.status.textContent = text || "";
  els.status.className = "status" + (kind ? " " + kind : "");
}

function setFieldError(input, errorEl, message) {
  input.setAttribute("aria-invalid", "true");
  errorEl.textContent = message;
  errorEl.hidden = false;
}

function clearFieldError(input, errorEl) {
  input.removeAttribute("aria-invalid");
  errorEl.textContent = "";
  errorEl.hidden = true;
}

function validateForm() {
  let firstInvalid = null;

  const links = els.links.value.split(/\s+/).map((s) => s.trim()).filter(Boolean);
  if (!links.length) {
    setFieldError(els.links, els.linksError, "Dán ít nhất một link Google Drive.");
    firstInvalid = els.links;
  } else {
    clearFieldError(els.links, els.linksError);
  }

  const outputDir = els.outputDir.value.trim();
  if (!outputDir) {
    setFieldError(els.outputDir, els.outputDirError, "Chọn thư mục để lưu video.");
    if (!firstInvalid) firstInvalid = els.outputDir;
  } else {
    clearFieldError(els.outputDir, els.outputDirError);
  }

  let limit = 0;
  if (els.limitMode.value === "limit") {
    const count = parseInt(els.limitCount.value, 10);
    if (!count || count < 1) {
      setFieldError(els.limitCount, els.limitError, "Nhập số video mỗi link (từ 1 trở lên).");
      if (!firstInvalid) firstInvalid = els.limitCount;
    } else {
      clearFieldError(els.limitCount, els.limitError);
      limit = count;
    }
  } else {
    clearFieldError(els.limitCount, els.limitError);
  }

  if (firstInvalid) {
    firstInvalid.focus();
    setStatus("Còn thông tin cần điền.", "error");
    return null;
  }

  return {
    links,
    outputDir,
    limit,
    concurrency: Math.max(1, Math.min(8, parseInt(els.concurrency.value, 10) || 3)),
    itag: parseInt(els.itag.value, 10) || 22,
  };
}

/* ------------------------------------------------------------------ */
/* Helpers                                                            */
/* ------------------------------------------------------------------ */
function formatBytes(n) {
  if (!n || n < 0) return "?";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return v.toFixed(v >= 10 || i === 0 ? 0 : 1) + " " + units[i];
}

function updateSummary() {
  if (!stats.links) {
    els.queueSummary.textContent = "";
    return;
  }
  els.queueSummary.textContent =
    stats.done + "/" + stats.total + " video · " + stats.links + " link";
}

function toggleLimitField() {
  els.limitField.hidden = els.limitMode.value !== "limit";
}

function renderPreview(groups) {
  els.previewList.innerHTML = "";
  let totalVideos = 0;
  let okLinks = 0;

  groups.forEach((group) => {
    const node = previewGroupTpl.content.firstElementChild.cloneNode(true);
    const nameEl = node.querySelector(".preview-name");
    nameEl.textContent = group.name || group.url;
    nameEl.title = group.url;
    const countEl = node.querySelector(".preview-count");

    if (group.error) {
      countEl.textContent = "lỗi";
      const errorEl = document.createElement("p");
      errorEl.className = "preview-error";
      errorEl.textContent = group.error;
      node.querySelector(".preview-items").replaceWith(errorEl);
    } else {
      okLinks += 1;
      totalVideos += group.videos.length;
      countEl.textContent = group.videos.length + " video";
      const list = node.querySelector(".preview-items");
      group.videos.forEach((name) => {
        const item = document.createElement("li");
        item.textContent = name;
        list.appendChild(item);
      });
    }
    els.previewList.appendChild(node);
  });

  els.preview.hidden = false;
  els.previewSummary.textContent =
    totalVideos + " video · " + okLinks + "/" + groups.length + " link đọc được";
  setStatus("Đã đọc danh sách video.", "ok");
}

/* ------------------------------------------------------------------ */
/* Queue rendering                                                    */
/* ------------------------------------------------------------------ */
function ensureCard(index, url) {
  if (cards[index]) return cards[index];
  const node = linkTpl.content.firstElementChild.cloneNode(true);
  node.querySelector(".idx").textContent = String(index + 1).padStart(2, "0");
  node.querySelector(".name").textContent = "Đang xử lý…";
  const urlEl = node.querySelector(".card-url");
  urlEl.textContent = url || "";
  urlEl.title = url || "";
  node.querySelector(".card-state").textContent = "đang xử lý";
  node.querySelector(".card-state").classList.add("running");
  els.empty.hidden = true;
  els.results.appendChild(node);
  cards[index] = {
    el: node,
    state: node.querySelector(".card-state"),
    files: {},
    done: 0,
    total: 0,
  };
  return cards[index];
}

function refreshCounts(card) {
  if (card.state.classList.contains("error")) return;
  card.state.textContent = card.done + "/" + card.total + " video";
}

function ensureFile(card, fileIndex, name) {
  if (card.files[fileIndex]) return card.files[fileIndex];
  const node = fileTpl.content.firstElementChild.cloneNode(true);
  const nameEl = node.querySelector(".file-name");
  nameEl.textContent = name || ("File #" + (fileIndex + 1));
  nameEl.title = name || "";
  node.querySelector(".file-meta").textContent = "bắt đầu…";
  card.el.querySelector(".files").appendChild(node);
  card.files[fileIndex] = {
    el: node,
    bar: node.querySelector(".bar"),
    fill: node.querySelector(".bar-fill"),
    meta: node.querySelector(".file-meta"),
  };
  return card.files[fileIndex];
}

function setBar(file, percent, label) {
  const value = Math.max(0, Math.min(100, percent));
  file.fill.style.width = value + "%";
  file.bar.setAttribute("aria-valuenow", value.toFixed(0));
  file.bar.setAttribute("aria-valuetext", label);
}

function handleEvent(ev) {
  const cardIndex = ev.index !== undefined ? ev.index : ev.link;
  const card = cardIndex !== undefined ? cards[cardIndex] : null;

  switch (ev.type) {
    case "link_start":
      ensureCard(ev.index, ev.url);
      break;

    case "link_resolved":
      if (card) {
        card.el.querySelector(".name").textContent = ev.name;
        card.total = ev.videos.length;
        card.done = 0;
        refreshCounts(card);
      }
      stats.total += ev.videos.length;
      updateSummary();
      if (!stats.done) setStatus("Đang tải " + stats.total + " video…");
      break;

    case "file_start":
      if (card) ensureFile(card, ev.file, ev.name).meta.textContent = "đang tải…";
      break;

    case "file_progress":
      if (card && card.files[ev.file]) {
        const file = card.files[ev.file];
        setBar(
          file,
          ev.total ? (ev.downloaded / ev.total) * 100 : 0,
          formatBytes(ev.downloaded) + " trên " + formatBytes(ev.total)
        );
        file.meta.textContent = formatBytes(ev.downloaded) + " / " + formatBytes(ev.total);
      }
      break;

    case "file_done":
      if (card && card.files[ev.file]) {
        const file = card.files[ev.file];
        file.el.classList.add("ok");
        setBar(file, 100, "hoàn tất");
        file.meta.textContent = ev.status === "skipped" ? "đã có sẵn" : "hoàn tất";
        card.done += 1;
        refreshCounts(card);
        stats.done += 1;
        updateSummary();
      }
      break;

    case "file_error":
      if (card && card.files[ev.file]) {
        const file = card.files[ev.file];
        file.el.classList.add("err");
        setBar(file, 100, "lỗi: " + ev.message);
        file.meta.textContent = ev.message;
        card.done += 1;
        refreshCounts(card);
        stats.done += 1;
        updateSummary();
      }
      break;

    case "link_done":
      if (card) {
        card.state.textContent = "xong";
        card.state.className = "card-state done";
      }
      stats.linksDone += 1;
      setStatus("Đang tải · xong " + stats.linksDone + "/" + stats.links + " link");
      break;

    case "link_aborted":
      if (card) {
        card.state.textContent = "đã hủy";
        card.state.className = "card-state error";
      }
      break;

    case "link_error":
      if (card) {
        card.state.textContent = "lỗi";
        card.state.className = "card-state error";
        const file = ensureFile(card, 0, ev.message || "Lỗi");
        file.el.classList.add("err");
        file.meta.textContent = "lỗi";
      }
      setStatus("Có link không tải được: " + (ev.message || "không rõ nguyên nhân"), "error");
      break;

    case "fatal":
      setStatus(ev.message, "error");
      break;

    case "done":
      setStatus("Xong · đã tải " + stats.done + "/" + stats.total + " video", "ok");
      finish();
      break;

    case "aborted":
      setStatus("Đã hủy · " + stats.done + "/" + stats.total + " video", "error");
      finish();
      break;
  }
}

function finish() {
  if (source) { source.close(); source = null; }
  els.results.setAttribute("aria-busy", "false");
  els.startBtn.disabled = false;
  els.cancelBtn.disabled = true;
  currentJob = "";
}

/* ------------------------------------------------------------------ */
/* Actions                                                            */
/* ------------------------------------------------------------------ */
async function start() {
  const form = validateForm();
  if (!form) return;

  els.results.innerHTML = "";
  els.results.setAttribute("aria-busy", "true");
  cards = {};
  stats = { links: form.links.length, linksDone: 0, total: 0, done: 0 };
  updateSummary();
  els.empty.hidden = true;
  setStatus("Đang chuẩn bị…");
  els.startBtn.disabled = true;
  els.cancelBtn.disabled = false;

  let res;
  try {
    res = await fetch("/api/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    }).then((r) => r.json());
  } catch (err) {
    els.startBtn.disabled = false;
    els.cancelBtn.disabled = true;
    els.results.setAttribute("aria-busy", "false");
    return setStatus("Không gọi được server: " + err, "error");
  }

  if (!res.ok) {
    els.startBtn.disabled = false;
    els.cancelBtn.disabled = true;
    els.results.setAttribute("aria-busy", "false");
    return setStatus(res.error || "Lỗi không xác định.", "error");
  }

  currentJob = res.jobId;
  source = new EventSource("/api/events?job=" + encodeURIComponent(currentJob));
  source.onmessage = (e) => handleEvent(JSON.parse(e.data));
}

async function cancel() {
  if (!currentJob) return;
  els.cancelBtn.disabled = true;
  setStatus("Đang hủy…");
  await fetch("/api/cancel", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jobId: currentJob }),
  }).catch(() => {});
}

async function pickFolder() {
  setStatus("Đang mở hộp thoại chọn thư mục…");
  els.pickBtn.disabled = true;
  try {
    const res = await fetch("/api/pick-folder", { method: "POST" }).then((r) => r.json());
    if (res.ok && res.path) {
      els.outputDir.value = res.path;
      clearFieldError(els.outputDir, els.outputDirError);
      setStatus("Đã chọn thư mục lưu.", "ok");
    } else if (res.ok) {
      setStatus("");
    } else {
      setStatus(res.error || "Không chọn được thư mục.", "error");
    }
  } catch (err) {
    setStatus("Lỗi: " + err, "error");
  } finally {
    els.pickBtn.disabled = false;
  }
}

async function preview() {
  const links = els.links.value.split(/\s+/).map((s) => s.trim()).filter(Boolean);
  if (!links.length) {
    setFieldError(els.links, els.linksError, "Dán ít nhất một link Google Drive.");
    els.links.focus();
    setStatus("Chưa có link nào để xem.", "error");
    return;
  }
  clearFieldError(els.links, els.linksError);

  els.previewBtn.disabled = true;
  setStatus("Đang đọc danh sách video…");
  try {
    const res = await fetch("/api/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ links }),
    }).then((r) => r.json());
    if (!res.ok) {
      setStatus(res.error || "Không đọc được danh sách.", "error");
      return;
    }
    renderPreview(res.groups);
  } catch (err) {
    setStatus("Không gọi được server: " + err, "error");
  } finally {
    els.previewBtn.disabled = false;
  }
}

/* ------------------------------------------------------------------ */
/* Init                                                               */
/* ------------------------------------------------------------------ */
async function init() {
  els.results.setAttribute("aria-busy", "false");

  els.setupForm.addEventListener("submit", (event) => {
    event.preventDefault();
    start();
  });
  els.cancelBtn.addEventListener("click", cancel);
  els.pickBtn.addEventListener("click", pickFolder);
  els.previewBtn.addEventListener("click", preview);
  els.emptyAction.addEventListener("click", () => els.links.focus());
  els.limitMode.addEventListener("change", toggleLimitField);
  toggleLimitField();

  els.outputDir.addEventListener("input", () =>
    clearFieldError(els.outputDir, els.outputDirError));
  els.limitCount.addEventListener("input", () =>
    clearFieldError(els.limitCount, els.limitError));
  els.links.addEventListener("input", () => {
    clearFieldError(els.links, els.linksError);
    // The preview belongs to the previous link list; hide it when that changes.
    els.preview.hidden = true;
  });

  try {
    const config = await fetch("/api/config").then((r) => r.json());
    if (config.outputDir && !els.outputDir.value) {
      els.outputDir.value = config.outputDir;
    }
  } catch (err) {
    /* config is optional; the user can type the path manually */
  }
}

init();
