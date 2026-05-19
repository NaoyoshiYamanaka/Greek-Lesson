/* Κοινή Drill — application logic
 * Single-file SPA with localStorage persistence and SRS scheduling.
 */

(function () {
  "use strict";

  // ---------- Storage layer ----------
  const STORAGE_KEY = "koine_drill_v1";

  function loadState() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return defaultState();
      const parsed = JSON.parse(raw);
      return Object.assign(defaultState(), parsed);
    } catch (e) {
      console.warn("State load failed", e);
      return defaultState();
    }
  }

  function defaultState() {
    return {
      version: 1,
      streak: { current: 0, longest: 0, lastSessionDate: null },
      totals: { answered: 0, correct: 0 },
      srs: {},          // questionId → {interval, ease, due, lastResult, misses}
      review: [],       // starred questionIds
      filter: {
        nouns: true,
        verbs: true,
        mode: "single", // "single" or "context"
      },
      errorPatterns: {},
      settings: {
        questionsPerSession: 50,
      },
    };
  }

  function saveState() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (e) {
      console.warn("State save failed", e);
    }
  }

  // ---------- SRS ----------
  function today() {
    const d = new Date();
    return d.toISOString().slice(0, 10);
  }

  function dateOffset(days) {
    const d = new Date();
    d.setDate(d.getDate() + days);
    return d.toISOString().slice(0, 10);
  }

  function updateSrs(qid, correct) {
    const s = state.srs[qid] || { interval: 0, ease: 2.5, due: today(), lastResult: null, misses: 0 };
    if (correct) {
      if (s.interval === 0) s.interval = 1;
      else if (s.interval === 1) s.interval = 3;
      else s.interval = Math.round(s.interval * s.ease);
      s.interval = Math.min(s.interval, 60);
      s.ease = Math.min(2.8, s.ease + 0.1);
      s.due = dateOffset(s.interval);
      s.lastResult = "correct";
    } else {
      s.interval = 0;
      s.ease = Math.max(1.5, s.ease - 0.2);
      s.due = today();
      s.lastResult = "wrong";
      s.misses = (s.misses || 0) + 1;
      if (!state.review.includes(qid)) state.review.push(qid);
    }
    state.srs[qid] = s;
  }

  function updateStreak() {
    const t = today();
    const last = state.streak.lastSessionDate;
    if (last === t) return; // already counted today
    if (last === dateOffset(-1)) state.streak.current += 1;
    else state.streak.current = 1;
    state.streak.longest = Math.max(state.streak.longest, state.streak.current);
    state.streak.lastSessionDate = t;
  }

  // ---------- Question pool & session ----------
  let QUESTIONS = window.QUESTIONS || [];
  let GLOSSES = window.GLOSSES || {};
  let questionsById = {};
  for (const q of QUESTIONS) questionsById[q.id] = q;

  function glossFor(lemma) {
    const g = GLOSSES[lemma];
    return (g && g.trim()) ? g : null;
  }

  // ---------- Resources modal ----------
  const RESOURCES = [
    {
      title: "ギリシア語パラダイム ダッシュボード",
      file: "docs/Greek_Paradigm_Dashboard.pdf",
      pages: 7,
      note: "主要パラダイムを俯瞰する一覧資料",
    },
    {
      title: "Biblical Greek Decoded",
      file: "docs/Biblical_Greek_Decoded.pdf",
      pages: 21,
      note: "聖書ギリシア語のしくみ解説",
    },
    {
      title: "Cowork 制作・パラダイム講義",
      file: "docs/Cowork_Paradigm_Lecture.pdf",
      pages: 36,
      note: "規則名詞・規則動詞（λύω）のスライド資料",
    },
  ];

  function openResources() {
    const root = document.getElementById("modal-root");
    if (!root) return;
    root.innerHTML = "";
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.addEventListener("click", (e) => { if (e.target === overlay) closeResources(); });
    const modal = document.createElement("div");
    modal.className = "modal";
    const header = document.createElement("div");
    header.className = "modal-header";
    const h2 = document.createElement("h2");
    h2.textContent = "📖 資料";
    const close = document.createElement("button");
    close.className = "modal-close";
    close.setAttribute("aria-label", "閉じる");
    close.textContent = "✕";
    close.addEventListener("click", closeResources);
    header.appendChild(h2);
    header.appendChild(close);
    modal.appendChild(header);
    const body = document.createElement("div");
    body.className = "modal-body";
    for (const r of RESOURCES) {
      const item = document.createElement("button");
      item.className = "resource-item";
      item.style.textAlign = "left";
      item.style.width = "100%";
      item.style.cursor = "pointer";
      const title = document.createElement("div");
      title.className = "r-title";
      title.innerHTML = `<span style="font-size:18px">📄</span><span>${r.title}</span>`;
      const meta = document.createElement("div");
      meta.className = "r-meta";
      meta.textContent = `PDF ・ ${r.pages} ページ`;
      const note = document.createElement("div");
      note.className = "r-note";
      note.textContent = r.note;
      item.appendChild(title);
      item.appendChild(meta);
      item.appendChild(note);
      item.addEventListener("click", () => {
        closeResources();
        openPdfViewer(r.file, r.title);
      });
      body.appendChild(item);
    }
    modal.appendChild(body);
    overlay.appendChild(modal);
    root.appendChild(overlay);
  }

  function closeResources() {
    const root = document.getElementById("modal-root");
    if (root) root.innerHTML = "";
  }

  function openPdfViewer(pdfUrl, title) {
    const root = document.getElementById("modal-root");
    if (!root) return;
    root.innerHTML = "";
    const overlay = document.createElement("div");
    overlay.className = "pdf-viewer-overlay";
    const header = document.createElement("div");
    header.className = "pdf-viewer-header";
    const titleEl = document.createElement("div");
    titleEl.className = "pdf-viewer-title";
    titleEl.textContent = title;
    const closeBtn = document.createElement("button");
    closeBtn.className = "pdf-viewer-close";
    closeBtn.textContent = "✕ 閉じる";
    closeBtn.addEventListener("click", closePdfViewer);
    header.appendChild(titleEl);
    header.appendChild(closeBtn);
    const iframe = document.createElement("iframe");
    iframe.src = pdfUrl;
    iframe.className = "pdf-viewer-frame";
    iframe.setAttribute("allow", "fullscreen");
    overlay.appendChild(header);
    overlay.appendChild(iframe);
    root.appendChild(overlay);
    // Lock body scroll while viewer is open
    document.body.style.overflow = "hidden";
  }

  function closePdfViewer() {
    const root = document.getElementById("modal-root");
    if (root) root.innerHTML = "";
    document.body.style.overflow = "";
  }

  // Wire up the header button (it exists in the static HTML)
  document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("resources-btn");
    if (btn) btn.addEventListener("click", openResources);
  });
  // Also handle the case where DOMContentLoaded already fired (since this script runs at end of body)
  const _existingBtn = document.getElementById("resources-btn");
  if (_existingBtn) _existingBtn.addEventListener("click", openResources);

  function filterQuestions() {
    const f = state.filter;
    return QUESTIONS.filter(q => {
      if (q.type === "noun" && !f.nouns) return false;
      if (q.type === "verb" && !f.verbs) return false;
      return true;
    });
  }

  function buildSession() {
    const pool = filterQuestions();
    const n = state.settings.questionsPerSession;
    const t = today();
    // 1. Due reviews (in SRS, due <= today)
    const due = pool.filter(q => state.srs[q.id] && state.srs[q.id].due <= t);
    // 2. Starred review (always rotate in)
    const starred = pool.filter(q => state.review.includes(q.id));
    // 3. Brand new
    const seen = new Set(Object.keys(state.srs));
    const fresh = pool.filter(q => !seen.has(q.id));

    const seenInSession = new Set();
    const result = [];
    function take(arr, count) {
      shuffle(arr);
      for (const q of arr) {
        if (result.length >= count) break;
        if (seenInSession.has(q.id)) continue;
        seenInSession.add(q.id);
        result.push(q);
      }
    }
    // Allocation heuristic: at least 30% starred (if any), 40% due, rest fresh
    take(starred, Math.min(starred.length, Math.floor(n * 0.3)));
    take(due, Math.floor(n * 0.7));
    take(fresh, n);
    // Top up from any source if still short
    take(pool, n);
    return result.slice(0, n);
  }

  function shuffle(a) {
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  // ---------- View rendering ----------
  const $app = document.getElementById("app");

  function el(tag, attrs = {}, ...kids) {
    const e = document.createElement(tag);
    for (const k in attrs) {
      if (k === "class") e.className = attrs[k];
      else if (k === "html") e.innerHTML = attrs[k];
      else if (k.startsWith("on")) e.addEventListener(k.slice(2).toLowerCase(), attrs[k]);
      else if (k === "data" && typeof attrs[k] === "object") {
        for (const dk in attrs[k]) e.dataset[dk] = attrs[k][dk];
      } else e.setAttribute(k, attrs[k]);
    }
    for (const kid of kids) {
      if (kid == null || kid === false) continue;
      if (typeof kid === "string") e.appendChild(document.createTextNode(kid));
      else e.appendChild(kid);
    }
    return e;
  }

  function render(view) { $app.innerHTML = ""; $app.appendChild(view); }

  // ---------- Home screen ----------
  function viewHome() {
    const accuracy = state.totals.answered > 0
      ? Math.round((state.totals.correct / state.totals.answered) * 100) : 0;
    const filter = state.filter;
    const session = buildSession();
    const pool = filterQuestions();

    const root = el("div", {});
    // Stats
    root.appendChild(el("div", { class: "home-stats" },
      el("div", { class: "home-stat" },
        el("div", { class: "num" }, String(state.streak.current)),
        el("div", { class: "lbl" }, "連続日数")),
      el("div", { class: "home-stat" },
        el("div", { class: "num" }, String(state.totals.answered)),
        el("div", { class: "lbl" }, "累積回答")),
      el("div", { class: "home-stat" },
        el("div", { class: "num" }, accuracy + "%"),
        el("div", { class: "lbl" }, "正答率")),
    ));

    // Recommended session
    const modeText = filter.mode === "single" ? "単独提示" : "節中提示";
    const rec = el("div", { class: "recommend-card" },
      el("h2", {}, "今日のひと押し"),
      el("p", {}, `${modeText}・${state.settings.questionsPerSession}問` +
        ` ／ 範囲：${filter.nouns ? "名詞" : ""}${filter.nouns && filter.verbs ? "＋" : ""}${filter.verbs ? "動詞" : ""}`),
      el("button", {
        class: "btn-primary",
        onclick: () => startSession(session),
      }, "はじめる"),
    );
    root.appendChild(rec);

    // Filter chips
    const fc = el("div", { class: "card" });
    fc.appendChild(el("div", { class: "card-title" }, "範囲"));
    const rowRange = el("div", { class: "filter-group" });
    rowRange.appendChild(chip("名詞", filter.nouns, () => { filter.nouns = !filter.nouns; if (!filter.nouns && !filter.verbs) filter.verbs = true; saveState(); render(viewHome()); }));
    rowRange.appendChild(chip("動詞", filter.verbs, () => { filter.verbs = !filter.verbs; if (!filter.nouns && !filter.verbs) filter.nouns = true; saveState(); render(viewHome()); }));
    fc.appendChild(rowRange);
    fc.appendChild(el("div", { class: "card-title", style: "margin-top:12px" }, "提示モード"));
    const rowMode = el("div", { class: "filter-group" });
    rowMode.appendChild(chip("単独提示", filter.mode === "single", () => { filter.mode = "single"; saveState(); render(viewHome()); }));
    rowMode.appendChild(chip("節中提示", filter.mode === "context", () => { filter.mode = "context"; saveState(); render(viewHome()); }));
    fc.appendChild(rowMode);
    root.appendChild(fc);

    // Navigation
    const nav = el("div", { class: "home-nav" },
      el("button", { onclick: () => render(viewReviewList()) },
        el("span", { class: "icon" }, "☆"),
        `復習帳 (${state.review.length})`),
      el("button", { onclick: () => render(viewSettings()) },
        el("span", { class: "icon" }, "⚙"),
        "設定"),
    );
    root.appendChild(nav);

    root.appendChild(el("div", { class: "small", style: "margin-top:20px;text-align:center" },
      `問題プール：${pool.length} 問`));
    return root;
  }

  function chip(label, on, onclick) {
    return el("button", { class: "chip" + (on ? " on" : ""), onclick }, label);
  }

  // ---------- Session screen ----------
  let session = null;

  function startSession(questions) {
    if (!questions || questions.length === 0) {
      alert("出題できる問題がありません。範囲を見直してください。");
      return;
    }
    session = {
      questions,
      idx: 0,
      correct: 0,
      answers: [], // {qid, correct, given}
      stage: "answering",
    };
    render(viewSession());
  }

  function viewSession() {
    if (!session || session.idx >= session.questions.length) return viewDone();
    const q = session.questions[session.idx];
    const root = el("div", {});

    // Top bar
    const pct = Math.round((session.idx / session.questions.length) * 100);
    const accuracy = session.idx > 0 ? Math.round((session.correct / session.idx) * 100) : 100;
    const bar = el("div", { class: "session-bar" },
      el("div", { class: "stat" }, `${session.idx + 1} / ${session.questions.length}`),
      el("div", { class: "progress" }, el("div", { class: "progress-fill", style: `width:${pct}%` })),
      el("div", { class: "stat" }, `☆${state.review.length}`),
      el("div", { class: "stat" }, `正答 ${accuracy}%`),
      el("button", { class: "quit-btn", onclick: confirmQuit }, "中断"),
    );
    root.appendChild(bar);

    // Question card
    const card = el("div", { class: "question-card" });

    // Context mode: show verse with target highlighted
    if (state.filter.mode === "context" && q.verseText && q.tokenIndex >= 0) {
      card.appendChild(el("div", { class: "question-ref" }, q.ref));
      const tokens = q.verseText.split(" ");
      const verseDiv = el("div", { class: "verse-context greek" });
      tokens.forEach((tok, i) => {
        if (i > 0) verseDiv.appendChild(document.createTextNode(" "));
        if (i === q.tokenIndex) {
          verseDiv.appendChild(el("span", { class: "target" }, tok));
        } else {
          verseDiv.appendChild(document.createTextNode(tok));
        }
      });
      card.appendChild(verseDiv);
      card.appendChild(el("div", { class: "target-prompt" }, "下線の語形をパースしてください"));
    } else {
      card.appendChild(el("div", { class: "target-form greek" }, q.form));
      card.appendChild(el("div", { class: "target-prompt" }, `辞書形：`,
        el("span", { class: "greek", style: "color:var(--ink);font-size:14px" }, q.lemma)));
    }

    const fields = q.type === "noun" ? nounFields(q) : verbFields(q);
    for (const f of fields) card.appendChild(f);

    card.appendChild(el("div", { class: "submit-row" },
      el("button", { class: "btn-primary", onclick: () => submitAnswer(q, fields) }, "答え合わせ"),
    ));

    root.appendChild(card);
    return root;
  }

  function selectField(label, name, options) {
    const row = el("div", { class: "answer-row" });
    row.appendChild(el("label", { for: name }, label));
    const sel = el("select", { id: name, name });
    sel.appendChild(el("option", { value: "" }, "—"));
    for (const opt of options) {
      sel.appendChild(el("option", { value: opt.v }, opt.t));
    }
    row.appendChild(sel);
    row.dataset.field = name;
    return row;
  }

  function nounFields(q) {
    return [
      selectField("Gender", "gender", [
        { v: "masculine", t: "Masc" }, { v: "feminine", t: "Fem" }, { v: "neuter", t: "Neut" },
      ]),
      selectField("Number", "number", [
        { v: "singular", t: "Sg" }, { v: "plural", t: "Pl" },
      ]),
      selectField("Case", "case", [
        { v: "nominative", t: "Nom" }, { v: "genitive", t: "Gen" },
        { v: "dative", t: "Dat" }, { v: "accusative", t: "Acc" },
        { v: "vocative", t: "Voc" },
      ]),
    ];
  }

  function verbFields(q) {
    return [
      selectField("Tense", "tense", [
        { v: "present", t: "Pres" }, { v: "imperfect", t: "Impf" },
        { v: "future", t: "Fut" }, { v: "aorist", t: "Aor" },
        { v: "perfect", t: "Perf" }, { v: "pluperfect", t: "Plpf" },
      ]),
      selectField("Voice", "voice", [
        { v: "active", t: "Act" }, { v: "middle", t: "Mid" }, { v: "passive", t: "Pass" },
      ]),
      selectField("Mood", "mood", [
        { v: "indicative", t: "Ind" }, { v: "subjunctive", t: "Subj" },
        { v: "imperative", t: "Impv" }, { v: "optative", t: "Opt" },
        { v: "infinitive", t: "Inf" }, { v: "participle", t: "Ptcp" },
      ]),
      selectField("Person", "person", [
        { v: "1", t: "1st" }, { v: "2", t: "2nd" }, { v: "3", t: "3rd" },
      ]),
      selectField("Number", "number", [
        { v: "singular", t: "Sg" }, { v: "plural", t: "Pl" },
      ]),
    ];
  }

  function submitAnswer(q, fields) {
    // Collect answer
    const given = {};
    for (const f of fields) {
      const sel = f.querySelector("select");
      if (sel.value) given[f.dataset.field] = sel.value;
    }
    // Compare with q.morph
    let correct = true;
    for (const key in q.morph) {
      if (key === "declension") continue; // not asked
      if (given[key] !== q.morph[key]) { correct = false; break; }
    }
    // For verb passive/middle: SBLGNT marks tense+voice; accept either middle or passive as long as morph matches one of them.
    // (Our generator already records "middle" or "passive" per morph code.)

    // Record
    session.answers.push({ qid: q.id, correct, given });
    if (correct) session.correct += 1;
    state.totals.answered += 1;
    if (correct) state.totals.correct += 1;
    updateSrs(q.id, correct);
    trackErrorPattern(q, given, correct);
    saveState();

    render(viewReview(q, correct, given));
  }

  function trackErrorPattern(q, given, correct) {
    if (correct) return;
    let key = null;
    if (q.type === "verb") {
      if (given.person && given.person !== q.morph.person) {
        key = `verb.person.${given.person}_vs_${q.morph.person}`;
      } else if (given.tense && given.tense !== q.morph.tense) {
        key = `verb.tense.${given.tense}_vs_${q.morph.tense}`;
      } else if (given.voice && given.voice !== q.morph.voice) {
        key = `verb.voice.${given.voice}_vs_${q.morph.voice}`;
      } else if (given.mood && given.mood !== q.morph.mood) {
        key = `verb.mood.${given.mood}_vs_${q.morph.mood}`;
      } else if (given.number && given.number !== q.morph.number) {
        key = `verb.number.${given.number}_vs_${q.morph.number}`;
      }
    } else {
      if (given.case && given.case !== q.morph.case) {
        key = `noun.case.${given.case}_vs_${q.morph.case}`;
      } else if (given.gender && given.gender !== q.morph.gender) {
        key = `noun.gender.${given.gender}_vs_${q.morph.gender}`;
      } else if (given.number && given.number !== q.morph.number) {
        key = `noun.number.${given.number}_vs_${q.morph.number}`;
      }
    }
    if (key) state.errorPatterns[key] = (state.errorPatterns[key] || 0) + 1;
  }

  // ---------- Answer review card ----------
  function viewReview(q, correct, given) {
    const root = el("div", {});

    // Top bar (same as session)
    const pct = Math.round(((session.idx + 1) / session.questions.length) * 100);
    const accuracy = Math.round((session.correct / (session.idx + 1)) * 100);
    root.appendChild(el("div", { class: "session-bar" },
      el("div", { class: "stat" }, `${session.idx + 1} / ${session.questions.length}`),
      el("div", { class: "progress" }, el("div", { class: "progress-fill", style: `width:${pct}%` })),
      el("div", { class: "stat" }, `☆${state.review.length}`),
      el("div", { class: "stat" }, `正答 ${accuracy}%`),
      el("button", { class: "quit-btn", onclick: confirmQuit }, "中断"),
    ));

    // Review card
    const card = el("div", { class: "review-card" });
    const head = el("div", { class: "review-header " + (correct ? "correct" : "wrong") });
    head.appendChild(el("div", { class: "review-mark" }, correct ? "✓" : "✗"));
    const sum = el("div", { class: "review-summary" });
    sum.appendChild(el("div", { class: "form-line greek" }, q.form,
      el("span", { style: "font-size:13px;color:var(--ink-3);margin-left:10px" }, "／"),
      el("span", { class: "greek", style: "font-size:16px;margin-left:6px" }, q.lemma)));
    sum.appendChild(el("div", { class: "parse-line" }, parseLine(q.morph, q.type)));
    // Gloss display
    const gloss = glossFor(q.lemma);
    if (gloss) {
      sum.appendChild(el("div", { class: "gloss-line" }, gloss));
    } else {
      sum.appendChild(el("div", { class: "gloss-line" },
        el("span", { class: "placeholder" }, "（語義未登録）")));
    }
    if (!correct) {
      sum.appendChild(el("div", { class: "yours" }, "あなた：" + parseLine(given, q.type, true)));
    }
    head.appendChild(sum);
    card.appendChild(head);

    // Body
    const body = el("div", { class: "review-body" });

    // Decomposition
    const decomp = el("div", { class: "decomp" });
    for (const seg of q.decomposition) {
      decomp.appendChild(el("div", { class: "decomp-seg", "data-role": seg.role },
        el("div", { class: "seg-text greek" }, seg.segment),
        el("div", { class: "seg-label" }, seg.label),
      ));
    }
    body.appendChild(el("div", { class: "review-section" },
      el("h3", {}, "語形の分解"),
      decomp,
    ));

    // Clues
    if (q.clues && q.clues.length) {
      const ul = el("ul", { class: "clue-list" });
      for (const c of q.clues) ul.appendChild(el("li", { html: highlightGreek(escapeHtml(c)) }));
      body.appendChild(el("div", { class: "review-section" },
        el("h3", {}, "この形から読み取れる手掛かり"),
        ul,
      ));
    }

    // Minimal pairs
    if (q.minimalPairs && q.minimalPairs.length) {
      const tbl = el("table", { class: "pair-table" });
      const thisRow = el("tr", { class: "this" },
        el("td", { class: "greek" }, q.form),
        el("td", {}, `${parseLine(q.morph, q.type, true)}　←今回`));
      tbl.appendChild(thisRow);
      for (const p of q.minimalPairs) {
        tbl.appendChild(el("tr", {},
          el("td", { class: "greek" }, p.form),
          el("td", {}, p.gloss),
        ));
      }
      body.appendChild(el("div", { class: "review-section" },
        el("h3", {}, "取り違えやすい類似形"),
        tbl,
      ));
    }

    // Error trend (only on wrong)
    if (!correct) {
      const trend = buildTrendText(q, given);
      if (trend) body.appendChild(el("div", { class: "review-section" },
        el("h3", {}, "あなたの傾向"),
        el("div", { class: "trend-box" }, trend),
      ));
    }

    card.appendChild(body);

    // Footer
    const footer = el("div", { class: "review-footer" });
    const starred = state.review.includes(q.id);
    const starBtn = el("button", {
      class: "btn-star" + (starred ? " added" : ""),
      onclick: () => {
        if (state.review.includes(q.id)) {
          state.review = state.review.filter(x => x !== q.id);
        } else {
          state.review.push(q.id);
        }
        saveState();
        render(viewReview(q, correct, given));
      },
    }, starred ? "☆ 復習帳に追加済" : "☆ 復習帳に追加");
    footer.appendChild(starBtn);
    footer.appendChild(el("button", {
      class: "btn-next",
      onclick: () => { session.idx += 1; render(viewSession()); },
    }, "次へ"));
    card.appendChild(footer);

    root.appendChild(card);
    return root;
  }

  function parseLine(morph, type, terse = false) {
    if (type === "verb") {
      const parts = [];
      if (morph.tense) parts.push({present:"Pres",imperfect:"Impf",future:"Fut",aorist:"Aor",perfect:"Perf",pluperfect:"Plpf"}[morph.tense] || morph.tense);
      if (morph.voice) parts.push({active:"Act",middle:"Mid",passive:"Pass"}[morph.voice] || morph.voice);
      if (morph.mood)  parts.push({indicative:"Ind",subjunctive:"Subj",imperative:"Impv",optative:"Opt",infinitive:"Inf",participle:"Ptcp"}[morph.mood] || morph.mood);
      if (morph.person && morph.number) {
        const ord = {"1":"1st","2":"2nd","3":"3rd"}[morph.person] || morph.person;
        const num = {singular:"Sg",plural:"Pl"}[morph.number] || morph.number;
        parts.push(ord + " " + num);
      } else {
        if (morph.person) parts.push({"1":"1st","2":"2nd","3":"3rd"}[morph.person] || morph.person);
        if (morph.number) parts.push({singular:"Sg",plural:"Pl"}[morph.number] || morph.number);
      }
      return parts.filter(Boolean).join(" ");
    } else {
      const parts = [];
      if (morph.gender) parts.push({masculine:"Masc",feminine:"Fem",neuter:"Neut"}[morph.gender] || morph.gender);
      if (morph.number) parts.push({singular:"Sg",plural:"Pl"}[morph.number] || morph.number);
      if (morph.case)   parts.push({nominative:"Nom",genitive:"Gen",dative:"Dat",accusative:"Acc",vocative:"Voc"}[morph.case] || morph.case);
      return parts.filter(Boolean).join(" ");
    }
  }

  function buildTrendText(q, given) {
    let key = null;
    if (q.type === "verb") {
      if (given.person && given.person !== q.morph.person) key = `verb.person.${given.person}_vs_${q.morph.person}`;
      else if (given.tense && given.tense !== q.morph.tense) key = `verb.tense.${given.tense}_vs_${q.morph.tense}`;
      else if (given.voice && given.voice !== q.morph.voice) key = `verb.voice.${given.voice}_vs_${q.morph.voice}`;
      else if (given.mood && given.mood !== q.morph.mood) key = `verb.mood.${given.mood}_vs_${q.morph.mood}`;
      else if (given.number && given.number !== q.morph.number) key = `verb.number.${given.number}_vs_${q.morph.number}`;
    } else {
      if (given.case && given.case !== q.morph.case) key = `noun.case.${given.case}_vs_${q.morph.case}`;
      else if (given.gender && given.gender !== q.morph.gender) key = `noun.gender.${given.gender}_vs_${q.morph.gender}`;
      else if (given.number && given.number !== q.morph.number) key = `noun.number.${given.number}_vs_${q.morph.number}`;
    }
    if (!key) return null;
    const count = state.errorPatterns[key] || 0;
    const desc = describePattern(key);
    if (count >= 2) {
      return `「${desc}」の取り違えが累計 ${count} 件あります。この対比をきちんと身体に入れ直すのがおすすめ。`;
    }
    return `「${desc}」の取り違え。次回までに対比を確認してください。`;
  }

  function describePattern(key) {
    const map = {
      person: ["1st","2nd","3rd"],
      tense: {present:"Pres",imperfect:"Impf",future:"Fut",aorist:"Aor",perfect:"Perf",pluperfect:"Plpf"},
      voice: {active:"Act",middle:"Mid",passive:"Pass"},
      mood: {indicative:"Ind",subjunctive:"Subj",imperative:"Impv",optative:"Opt",infinitive:"Inf",participle:"Ptcp"},
      case: {nominative:"Nom",genitive:"Gen",dative:"Dat",accusative:"Acc",vocative:"Voc"},
      number: {singular:"Sg",plural:"Pl"},
      gender: {masculine:"Masc",feminine:"Fem",neuter:"Neut"},
    };
    const m = key.match(/^(\w+)\.(\w+)\.(.+)_vs_(.+)$/);
    if (!m) return key;
    const dim = m[2];
    const a = m[3], b = m[4];
    const label = (v) => (Array.isArray(map[dim])) ? (map[dim][parseInt(v)-1] || v) : ((map[dim] || {})[v] || v);
    return `${label(a)} ⇔ ${label(b)}`;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[c]);
  }
  function highlightGreek(s) {
    // Wrap Greek runs in a span.greek to preserve typography. Greek block: U+0370–U+03FF, U+1F00–U+1FFF.
    return s.replace(/([Ͱ-Ͽἀ-῿][Ͱ-Ͽἀ-῿\(\)ν.\-]*)/g, '<span class="greek">$1</span>');
  }

  function confirmQuit() {
    if (confirm("セッションを中断しますか？\n進捗（正答数・SRS）は保存されます。")) {
      render(viewHome());
    }
  }

  // ---------- Session done screen ----------
  function viewDone() {
    updateStreak();
    saveState();
    const accuracy = Math.round((session.correct / session.questions.length) * 100);
    const root = el("div", {});
    const card = el("div", { class: "card done-card" },
      el("h2", {}, "セッション完了"),
      el("div", {},
        el("div", { class: "done-stat" },
          el("div", { class: "num" }, `${session.correct} / ${session.questions.length}`),
          el("div", { class: "lbl" }, "正答")),
        el("div", { class: "done-stat" },
          el("div", { class: "num" }, accuracy + "%"),
          el("div", { class: "lbl" }, "正答率")),
        el("div", { class: "done-stat" },
          el("div", { class: "num" }, String(state.streak.current)),
          el("div", { class: "lbl" }, "連続日数")),
      ),
      topErrorPatternsView(),
      el("div", { class: "done-actions" },
        el("button", { class: "btn-secondary", onclick: () => render(viewHome()) }, "ホームへ"),
        el("button", { class: "btn-primary", onclick: () => startSession(buildSession()) }, "もう1セット"),
      ),
    );
    root.appendChild(card);
    return root;
  }

  function topErrorPatternsView() {
    const entries = Object.entries(state.errorPatterns).sort((a, b) => b[1] - a[1]).slice(0, 3);
    if (entries.length === 0) return el("div", {});
    const box = el("div", { class: "card", style: "margin-top:20px;text-align:left" });
    box.appendChild(el("div", { class: "card-title" }, "苦手の傾向（累計）"));
    for (const [k, n] of entries) {
      box.appendChild(el("div", { style: "font-size:13px;padding:4px 0;color:var(--ink-2)" },
        describePattern(k) + " — " + n + "件"));
    }
    return box;
  }

  // ---------- Review list ----------
  function viewReviewList() {
    const root = el("div", {});
    root.appendChild(el("button", {
      class: "btn-secondary", style: "margin-bottom:14px",
      onclick: () => render(viewHome()),
    }, "← ホーム"));
    root.appendChild(el("div", { class: "card-title" }, `☆ 復習帳（${state.review.length}）`));
    if (state.review.length === 0) {
      root.appendChild(el("div", { class: "empty" }, "まだ復習帳に登録されている語形はありません。"));
      return root;
    }
    const ul = el("ul", { class: "review-list" });
    for (const qid of state.review.slice().reverse()) {
      const q = questionsById[qid];
      if (!q) continue;
      ul.appendChild(el("li", {},
        el("div", { class: "lform greek" }, q.form),
        el("div", { style: "text-align:right;flex:1" },
          el("div", { class: "lparse" }, parseLine(q.morph, q.type)),
          el("div", { class: "lref" }, q.ref + " ・ " + q.lemma)),
      ));
    }
    root.appendChild(ul);
    root.appendChild(el("div", { style: "margin-top:16px;text-align:center" },
      el("button", { class: "btn-primary", onclick: () => startSession(starredSession()) }, "復習帳だけで演習"),
    ));
    return root;
  }

  function starredSession() {
    const ids = state.review;
    const qs = ids.map(id => questionsById[id]).filter(Boolean);
    shuffle(qs);
    return qs.slice(0, state.settings.questionsPerSession);
  }

  // ---------- Settings ----------
  function viewSettings() {
    const root = el("div", {});
    root.appendChild(el("button", {
      class: "btn-secondary", style: "margin-bottom:14px",
      onclick: () => render(viewHome()),
    }, "← ホーム"));
    const card = el("div", { class: "card" });
    card.appendChild(el("div", { class: "card-title" }, "設定"));
    // Questions per session
    const r1 = el("div", { class: "settings-row" });
    r1.appendChild(el("label", {}, "1セッションの問題数"));
    const sel = el("select", {});
    for (const n of [20, 30, 50, 80, 100]) {
      const opt = el("option", { value: String(n) }, `${n} 問`);
      if (n === state.settings.questionsPerSession) opt.selected = true;
      sel.appendChild(opt);
    }
    sel.addEventListener("change", () => {
      state.settings.questionsPerSession = parseInt(sel.value, 10);
      saveState();
    });
    r1.appendChild(sel);
    card.appendChild(r1);

    // Reset button
    const r2 = el("div", { class: "settings-row" });
    r2.appendChild(el("label", { class: "danger" }, "進捗をリセット"));
    r2.appendChild(el("button", {
      class: "btn-secondary", style: "color:var(--wrong);border-color:var(--wrong)",
      onclick: () => {
        if (confirm("すべての進捗・SRS・復習帳を消去します。よろしいですか？")) {
          state = defaultState(); saveState(); render(viewHome());
        }
      },
    }, "リセット"));
    card.appendChild(r2);
    root.appendChild(card);

    root.appendChild(el("div", { class: "small", style: "text-align:center;margin-top:24px;line-height:1.7" },
      "Κοινή Drill v0.1 ・ 山中尚義 個人用 ・ ",
      el("br"),
      "本文・形態素タグ：MorphGNT / SBLGNT (CC BY 4.0 + CC BY-SA 3.0)"));
    return root;
  }

  // ---------- Boot ----------
  let state = loadState();
  render(viewHome());

  // Expose for debugging
  window._state = () => state;
  window._questions = QUESTIONS;
})();
