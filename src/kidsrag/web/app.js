// Ask the Book - page behaviour. No framework; the page has one job.
"use strict";

const $ = (id) => document.getElementById(id);

const LETTER_A = "01000001";

const TAGS = {
  welcome: "Hello!",
  answer: "From the book",
  refusal: "Not in this chapter",
  trouble: "Oops",
};

let lastRetrieval = null;
let flipTimer = null;

// ---------- Bits ----------

function drawBits(el, pattern) {
  el.replaceChildren(
    ...[...pattern].map((b) => {
      const s = document.createElement("span");
      s.className = "bit" + (b === "1" ? " on" : "");
      return s;
    })
  );
}

function startFlipping(el) {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  drawBits(el, LETTER_A);
  if (reduce) return;
  flipTimer = setInterval(() => {
    const bits = el.children;
    bits[Math.floor(Math.random() * bits.length)].classList.toggle("on");
  }, 110);
}

function stopFlipping() {
  clearInterval(flipTimer);
  flipTimer = null;
}

// ---------- Tiny, safe markdown (bold, italics, lists, paragraphs) ----------

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

function inline(s) {
  return escapeHtml(s)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*(?!\s)(.+?)\*(?!\*)/g, "$1<em>$2</em>");
}

function markdown(text) {
  const out = [];
  for (const block of text.trim().split(/\n{2,}/)) {
    const lines = block.split("\n");
    if (lines.every((l) => /^\s*[-*•]\s+/.test(l))) {
      out.push("<ul>" + lines.map((l) => `<li>${inline(l.replace(/^\s*[-*•]\s+/, ""))}</li>`).join("") + "</ul>");
    } else if (lines.every((l) => /^\s*\d+[.)]\s+/.test(l))) {
      out.push("<ol>" + lines.map((l) => `<li>${inline(l.replace(/^\s*\d+[.)]\s+/, ""))}</li>`).join("") + "</ol>");
    } else {
      out.push(`<p>${lines.map(inline).join("<br>")}</p>`);
    }
  }
  return out.join("");
}

// ---------- Rendering ----------

function showAnswer(kind, text, question) {
  const card = $("answer");
  card.className = "answer " + kind;
  // Restart the entrance animation for each new answer.
  void card.offsetWidth;
  $("answer-tag").textContent = TAGS[kind] || TAGS.answer;
  $("asked").hidden = !question;
  $("asked").textContent = question || "";
  $("answer-body").innerHTML = markdown(text);
}

function showThinking(question) {
  const card = $("answer");
  card.className = "answer";
  $("answer-tag").textContent = "Searching the book";
  $("asked").hidden = false;
  $("asked").textContent = question;
  const wrap = document.createElement("div");
  wrap.className = "thinking";
  const bits = document.createElement("div");
  bits.className = "bits";
  const label = document.createElement("span");
  label.textContent = "Looking through the pages…";
  wrap.append(bits, label);
  $("answer-body").replaceChildren(wrap);
  startFlipping(bits);
}

function pageLabel(url) {
  const m = url.match(/p0*(\d+)\.png$/);
  return m ? `Page ${m[1]}` : "Book page";
}

function showPages(images) {
  const grid = $("page-grid");
  grid.replaceChildren();
  $("pages").hidden = images.length === 0;
  $("result").classList.toggle("has-pages", images.length > 0);
  images.forEach((url, i) => {
    const label = pageLabel(url);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "page";
    btn.style.animationDelay = `${80 * i}ms`;
    btn.setAttribute("aria-label", `Open ${label} bigger`);
    const img = document.createElement("img");
    img.src = url;
    img.alt = `${label} of the book`;
    img.loading = "lazy";
    const cap = document.createElement("span");
    cap.textContent = label;
    btn.append(img, cap);
    btn.addEventListener("click", () => openLightbox(url, label));
    grid.append(btn);
  });
}

function openLightbox(url, label) {
  $("lightbox-img").src = url;
  $("lightbox-img").alt = `${label} of the book`;
  $("lightbox-cap").textContent = label;
  $("lightbox").showModal();
}

// ---------- Reviewer drawer ----------

function renderRetrieval(r) {
  const body = $("drawer-body");
  if (!r) {
    body.textContent = "Ask a question first.";
    return;
  }
  const gateClass = r.gate === "PASS" ? "gate-pass" : "gate-refuse";
  const rows = r.rows.map((row) => `
    <tr>
      <td class="num">${row.rank}</td>
      <td class="num">${row.fused.toFixed(5)}</td>
      <td class="num">${row.dense ?? "–"}</td>
      <td class="num">${row.sparse ?? "–"}</td>
      <td>${escapeHtml(row.heading)}<span class="pg">p. ${row.pages.join(", ")}</span></td>
    </tr>`).join("");
  body.innerHTML = `
    <div class="stats">
      <div class="stat ${gateClass}"><b>${r.gate}</b><small>gate</small></div>
      <div class="stat"><b>${r.max_cosine.toFixed(4)}</b><small>max cosine (min ${r.min_cosine})</small></div>
      <div class="stat"><b>${r.top_fused.toFixed(5)}</b><small>top fused (RRF)</small></div>
    </div>
    <table class="rtable">
      <thead><tr><th>#</th><th>Fused</th><th>Dense</th><th>Sparse</th><th>Passage</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

// ---------- Asking ----------

async function ask(question) {
  question = question.trim();
  if (!question) return;

  const input = $("question");
  const btn = $("ask-btn");
  input.value = question;
  btn.disabled = true;
  showPages([]);
  showThinking(question);

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    stopFlipping();
    showAnswer(data.kind, data.text, question);
    showPages(data.images || []);
    lastRetrieval = data.retrieval;
    $("open-reviewer").disabled = !lastRetrieval;
  } catch {
    // Same wording as render.TROUBLE_TEXT: the server never got to answer.
    stopFlipping();
    showAnswer(
      "trouble",
      "Something went wrong on my side, sorry about that!\n\n" +
        "It's not a problem with your question. Please try asking again in a moment.",
      question
    );
  } finally {
    btn.disabled = false;
    input.focus();
  }
}

// ---------- Start ----------

async function init() {
  drawBits($("brand-bits"), LETTER_A);

  $("ask-form").addEventListener("submit", (e) => {
    e.preventDefault();
    ask($("question").value);
  });

  $("open-reviewer").addEventListener("click", () => {
    renderRetrieval(lastRetrieval);
    $("drawer").showModal();
  });

  // Click outside a dialog's content to close it.
  for (const d of [$("lightbox"), $("drawer")]) {
    d.addEventListener("click", (e) => { if (e.target === d) d.close(); });
  }

  try {
    const meta = await (await fetch("/api/meta")).json();
    $("chapter").textContent = `Chapter: ${meta.chapter}`;
    showAnswer("welcome", meta.welcome, "");
    for (const q of meta.examples) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip";
      chip.textContent = q;
      chip.addEventListener("click", () => ask(q));
      $("examples").append(chip);
    }
  } catch {
    $("chapter").textContent = "";
  }

  // A link like /#q=What%20is%20binary%20code%3F asks straight away.
  const linked = new URLSearchParams(location.hash.slice(1)).get("q");
  if (linked) ask(linked);
  else $("question").focus();
}

init();
