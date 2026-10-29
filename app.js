// MolView Bench front end: talks to /api/analyze and renders the table, 2D cards and 3D viewers.
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const root = document.documentElement;

  const input = $("#smiles-input");
  const analyzeBtn = $("#analyze-btn");
  const loading = $("#loading");
  const messages = $("#messages");
  const resultsSection = $("#results");
  const tbody = $("#props-table tbody");
  const grid2d = $("#grid-2d");
  const grid3d = $("#grid-3d");
  const styleSelect = $("#style-select");
  const themeBtn = $("#theme-toggle");

  const COLUMNS = ["smiles", "canonical", "MW", "logP", "HBD", "HBA", "TPSA"];

  let results = [];          // current rows, each tagged with a stable idx
  let viewers = [];          // { idx, viewer }
  let sortState = { key: null, dir: 1 };

  // ---------- Theme ----------

  function currentTheme() {
    return root.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function cssVar(name) {
    return getComputedStyle(root).getPropertyValue(name).trim();
  }

  function updateThemeButton() {
    const next = currentTheme() === "dark" ? "light" : "dark";
    themeBtn.setAttribute("aria-label", `Switch to ${next} mode`);
  }

  function setTheme(theme, persist) {
    root.setAttribute("data-theme", theme);
    if (persist) {
      try { localStorage.setItem("theme", theme); } catch (e) { /* private mode, no big deal */ }
    }
    updateThemeButton();
    restyleViewers();
  }

  themeBtn.addEventListener("click", () => {
    setTheme(currentTheme() === "dark" ? "light" : "dark", true);
  });

  // Keep following the OS setting until the user makes an explicit choice
  if (window.matchMedia) {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e) => {
      let saved = null;
      try { saved = localStorage.getItem("theme"); } catch (err) {}
      if (!saved) setTheme(e.matches ? "dark" : "light", false);
    };
    if (mq.addEventListener) mq.addEventListener("change", onChange);
    else if (mq.addListener) mq.addListener(onChange);
  }
  updateThemeButton();

  // ---------- Examples & input ----------

  const exampleBtns = document.querySelectorAll("[data-example]");
  exampleBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const smi = btn.dataset.example;
      const lines = input.value.split("\n").map((l) => l.trim()).filter(Boolean);
      if (!lines.includes(smi)) lines.push(smi);
      input.value = lines.join("\n");
      input.focus();
    });
  });

  $("[data-example-set='all']").addEventListener("click", () => {
    input.value = Array.from(exampleBtns, (b) => b.dataset.example).join("\n");
    input.focus();
  });

  $("#clear-btn").addEventListener("click", () => {
    input.value = "";
    messages.innerHTML = "";
    resultsSection.hidden = true;
    clearViewers();
    input.focus();
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      analyze();
    }
  });

  analyzeBtn.addEventListener("click", analyze);

  // ---------- Analysis ----------

  async function analyze() {
    const smiles = input.value.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
    messages.innerHTML = "";

    if (!smiles.length) {
      showMessage("warning", "Nothing to analyze", ["Enter at least one SMILES string, one per line."]);
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ smiles }),
      });

      let data = null;
      try { data = await res.json(); } catch (e) { /* non-JSON, handled below */ }

      if (!res.ok || !data) {
        const reason = (data && data.error) ||
          `The analysis server answered with status ${res.status}. Make sure the Flask backend (app.py) is running.`;
        showMessage("error", "Analysis failed", [reason]);
        return;
      }

      results = (data.results || []).map((r, i) => ({ ...r, idx: i }));
      sortState = { key: null, dir: 1 };
      renderErrors(data.errors || []);
      renderAll();
    } catch (err) {
      showMessage("error", "Could not reach the analysis server", [
        "The request didn't go through. Check that the Flask app is running (python app.py) and try again.",
      ]);
    } finally {
      setLoading(false);
    }
  }

  function setLoading(on) {
    loading.hidden = !on;
    analyzeBtn.disabled = on;
    analyzeBtn.textContent = on ? "Analyzing..." : "Analyze";
    resultsSection.setAttribute("aria-busy", on ? "true" : "false");
  }

  // ---------- Messages ----------

  function showMessage(kind, title, items) {
    const box = document.createElement("div");
    box.className = `msg msg-${kind}`;
    box.setAttribute("role", kind === "error" ? "alert" : "status");
    const h = document.createElement("h3");
    h.textContent = title;
    const ul = document.createElement("ul");
    items.forEach((item) => {
      const li = document.createElement("li");
      if (typeof item === "string") li.textContent = item;
      else li.append(...item);
      ul.appendChild(li);
    });
    box.append(h, ul);
    messages.appendChild(box);
  }

  function renderErrors(errors) {
    if (!errors.length) return;
    const items = errors.map((err) => {
      const code = document.createElement("code");
      code.textContent = err.smiles;
      return [code, document.createTextNode(` : ${err.message}`)];
    });
    const n = errors.length;
    showMessage("error", `${n} invalid SMILES ${n === 1 ? "was" : "were"} skipped`, items);
  }

  // ---------- Rendering ----------

  function renderAll() {
    resultsSection.hidden = results.length === 0;
    renderTable();
    render2D();
    render3D();
  }

  function fmt(v) {
    return typeof v === "number" ? String(v) : (v == null ? "" : String(v));
  }

  function renderTable() {
    tbody.innerHTML = "";
    sortedResults().forEach((r) => {
      const tr = document.createElement("tr");
      tr.dataset.idx = r.idx;
      COLUMNS.forEach((key) => {
        const td = document.createElement("td");
        td.textContent = fmt(r[key]);
        td.className = typeof r[key] === "number" ? "num" : "mono";
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });

    document.querySelectorAll("#props-table th").forEach((th) => {
      if (th.dataset.key === sortState.key) {
        th.setAttribute("aria-sort", sortState.dir === 1 ? "ascending" : "descending");
      } else {
        th.removeAttribute("aria-sort");
      }
    });
  }

  function sortedResults() {
    if (!sortState.key) return results.slice();
    const { key, dir } = sortState;
    return results.slice().sort((a, b) => {
      const x = a[key], y = b[key];
      if (typeof x === "number" && typeof y === "number") return (x - y) * dir;
      return String(x).localeCompare(String(y)) * dir;
    });
  }

  document.querySelectorAll("#props-table th button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.parentElement.dataset.key;
      // First click sorts ascending, second descending, third goes back to input order
      if (sortState.key !== key) sortState = { key, dir: 1 };
      else if (sortState.dir === 1) sortState.dir = -1;
      else sortState = { key: null, dir: 1 };
      renderTable();
    });
  });

  function makeCaption(r) {
    const cap = document.createElement("figcaption");
    cap.className = "card-caption";
    const badge = document.createElement("span");
    badge.className = "card-index";
    badge.textContent = `#${r.idx + 1}`;
    const text = document.createElement("span");
    text.textContent = r.smiles;
    cap.append(badge, text);
    return cap;
  }

  function render2D() {
    grid2d.innerHTML = "";
    results.forEach((r) => {
      const card = document.createElement("figure");
      card.className = "card";
      card.style.margin = "0";
      card.dataset.idx = r.idx;

      const fig = document.createElement("div");
      fig.className = "card-figure";
      // Both drawings live in the DOM; CSS shows the one for the current theme
      const light = document.createElement("div");
      light.className = "svg-light";
      light.innerHTML = r.svg_light || "";
      const dark = document.createElement("div");
      dark.className = "svg-dark";
      dark.innerHTML = r.svg_dark || "";
      fig.append(light, dark);
      fig.setAttribute("role", "img");
      fig.setAttribute("aria-label", `2D structure of ${r.smiles}`);

      card.append(fig, makeCaption(r));
      grid2d.appendChild(card);
    });
  }

  // ---------- 3D ----------

  function clearViewers() {
    viewers.forEach(({ viewer }) => { try { viewer.clear(); } catch (e) {} });
    viewers = [];
    grid3d.innerHTML = "";
  }

  // Element colors per theme: hydrogens are white by default, which vanishes on a light
  // background, so we tint them gray in light mode via a CSS variable.
  function colorScheme() {
    const base = (window.$3Dmol && $3Dmol.elementColors && $3Dmol.elementColors.Jmol) || null;
    if (!base) return "Jmol";
    const h = parseInt(cssVar("--viewer-hydrogen").replace("#", ""), 16);
    return { prop: "elem", map: Object.assign({}, base, { H: h }) };
  }

  function styleSpec(name) {
    const colorscheme = colorScheme();
    switch (name) {
      case "stick":
        return { stick: { radius: 0.17, colorscheme } };
      case "sphere":
        return { sphere: { scale: 0.95, colorscheme } };
      default:
        return { stick: { radius: 0.13, colorscheme }, sphere: { scale: 0.27, colorscheme } };
    }
  }

  function applyStyle(viewer) {
    viewer.setBackgroundColor(cssVar("--viewer-bg"));
    viewer.setStyle({}, styleSpec(styleSelect.value));
    viewer.render();
  }

  function restyleViewers() {
    viewers.forEach(({ viewer }) => applyStyle(viewer));
  }

  styleSelect.addEventListener("change", restyleViewers);

  function render3D() {
    clearViewers();
    results.forEach((r) => {
      const card = document.createElement("figure");
      card.className = "card";
      card.style.margin = "0";
      card.dataset.idx = r.idx;

      const box = document.createElement("div");
      box.className = "viewer";
      card.append(box, makeCaption(r));
      grid3d.appendChild(card);

      if (!r.molblock_3d) {
        box.classList.add("viewer-failed");
        box.textContent = "3D generation failed";
        return;
      }
      if (!window.$3Dmol) {
        box.classList.add("viewer-failed");
        box.textContent = "3D viewer could not load (3Dmol.js unavailable)";
        return;
      }

      try {
        const viewer = $3Dmol.createViewer(box, { backgroundColor: cssVar("--viewer-bg") });
        viewer.addModel(r.molblock_3d, "sdf");
        applyStyle(viewer);
        viewer.zoomTo();
        viewer.render();
        viewers.push({ idx: r.idx, viewer });
      } catch (e) {
        box.classList.add("viewer-failed");
        box.textContent = "3D generation failed";
      }
    });
  }

  // Keep viewers sized correctly when the layout changes
  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => viewers.forEach(({ viewer }) => { viewer.resize(); viewer.render(); }), 120);
  });

  // ---------- Linking row <-> cards on hover ----------

  function highlight(idx, on) {
    document.querySelectorAll(`[data-idx="${idx}"]`).forEach((el) => el.classList.toggle("is-linked", on));
  }

  function bindHover(container, selector) {
    container.addEventListener("mouseover", (e) => {
      const el = e.target.closest(selector);
      if (el) highlight(el.dataset.idx, true);
    });
    container.addEventListener("mouseout", (e) => {
      const el = e.target.closest(selector);
      if (el && !el.contains(e.relatedTarget)) highlight(el.dataset.idx, false);
    });
  }
  bindHover(tbody, "tr");
  bindHover(grid2d, ".card");
  bindHover(grid3d, ".card");

  // ---------- CSV ----------

  function csvCell(v) {
    const s = fmt(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  }

  $("#csv-btn").addEventListener("click", () => {
    if (!results.length) return;
    const header = ["SMILES", "Canonical SMILES", "MW", "logP", "HBD", "HBA", "TPSA"];
    const lines = [header.join(",")].concat(
      sortedResults().map((r) => COLUMNS.map((k) => csvCell(r[k])).join(","))
    );
    const blob = new Blob([lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "molecular_properties.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
})();
