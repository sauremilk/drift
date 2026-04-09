/**
 * Drift "Prove It Yourself" — Browser-based Repo Analyzer & Results Viewer.
 *
 * Primary flow: User enters a public GitHub repo URL → code is fetched via
 * GitHub's REST API → lightweight Python analysis runs in-browser → findings
 * are rendered as interactive cards.
 *
 * Secondary flow: User drops a local drift-results.json (from a full
 * `drift analyze` run) for rendering.
 *
 * All processing happens client-side. No data leaves the browser.
 *
 * @license MIT
 */
(function () {
  "use strict";

  /* ── Config ──────────────────────────────────── */

  var GITHUB_API = "https://api.github.com";
  var MAX_FILES = 30;
  var BATCH = 6;

  var SEV_COLOR = {
    critical: "#ef4444", high: "#f97316", medium: "#eab308",
    low: "#3b82f6", info: "#6b7280"
  };
  var SEV_LABEL = {
    critical: "Critical", high: "High", medium: "Medium",
    low: "Low", info: "Info"
  };

  var SKIP_DIR = /^(tests?|testing|spec|__pycache__|\.?venv|env|\.git|node_modules|site-packages|\.tox|\.mypy_cache|\.pytest_cache|migrations?|docs?|examples?|build|dist|\.eggs?|\.nox)$/i;
  var SKIP_FILE = /^(setup\.py|conftest\.py|manage\.py|wsgi\.py|asgi\.py|__main__\.py|noxfile\.py|fabfile\.py)$/i;
  var COMMON_FN = [
    "__init__","__str__","__repr__","__eq__","__hash__",
    "__lt__","__le__","__gt__","__ge__","__len__","__iter__",
    "__next__","__enter__","__exit__","__call__","__getattr__",
    "__setattr__","__delattr__","__getitem__","__setitem__",
    "__contains__","__bool__","__del__","__new__",
    "setUp","tearDown","setUpClass","tearDownClass","main","run"
  ];

  /* ── DOM helpers ─────────────────────────────── */

  function el(tag, cls, txt) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt !== undefined) n.textContent = txt;
    return n;
  }

  function fmtScore(n) {
    return typeof n === "number" ? n.toFixed(3) : "\u2014";
  }

  /* ── GitHub API ──────────────────────────────── */

  function parseRepoUrl(raw) {
    var m = raw.trim().match(/github\.com\/([A-Za-z0-9_.-]+)\/([A-Za-z0-9_.-]+)/);
    if (!m) return null;
    return { owner: m[1], repo: m[2].replace(/\.git$/, "").replace(/\/$/, "") };
  }

  function ghGet(path) {
    return fetch(GITHUB_API + path, {
      headers: { Accept: "application/vnd.github.v3+json" }
    }).then(function (r) {
      if (r.status === 403) {
        return r.json().catch(function () { return {}; }).then(function (b) {
          if (b.message && b.message.indexOf("rate limit") > -1)
            throw new Error("RATE_LIMIT");
          throw new Error("ACCESS_DENIED");
        });
      }
      if (r.status === 404) throw new Error("NOT_FOUND");
      if (!r.ok) throw new Error("API_ERROR:" + r.status);
      return r.json();
    });
  }

  function decodeBlob(b64) {
    var bin = atob(b64.replace(/\s/g, ""));
    var bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new TextDecoder("utf-8").decode(bytes);
  }

  /* ── File selection ──────────────────────────── */

  function selectPyFiles(tree) {
    var pyFiles = tree.filter(function (n) {
      if (n.type !== "blob" || !n.path.endsWith(".py")) return false;
      var parts = n.path.split("/");
      for (var i = 0; i < parts.length - 1; i++) {
        if (SKIP_DIR.test(parts[i])) return false;
      }
      return !SKIP_FILE.test(parts[parts.length - 1]);
    });
    pyFiles.sort(function (a, b) {
      var da = a.path.split("/").length, db = b.path.split("/").length;
      return da !== db ? db - da : (b.size || 0) - (a.size || 0);
    });
    return pyFiles.slice(0, MAX_FILES);
  }

  function fetchContents(owner, repo, files, onStatus) {
    var results = [];
    var idx = 0;

    function nextBatch() {
      if (idx >= files.length) return Promise.resolve(results);
      var batch = files.slice(idx, idx + BATCH);
      var n1 = idx + 1, n2 = Math.min(idx + BATCH, files.length);
      onStatus("Fetching files " + n1 + "\u2013" + n2 + " of " + files.length + "\u2026");
      idx += BATCH;

      var promises = batch.map(function (f) {
        return ghGet("/repos/" + owner + "/" + repo + "/git/blobs/" + f.sha)
          .then(function (b) {
            return { path: f.path, content: decodeBlob(b.content), size: b.size };
          })
          .catch(function () { return null; });
      });

      return Promise.all(promises).then(function (settled) {
        for (var i = 0; i < settled.length; i++) {
          if (settled[i]) {
            settled[i].lineCount = settled[i].content.split("\n").length;
            results.push(settled[i]);
          }
        }
        return nextBatch();
      });
    }

    return nextBatch();
  }

  /* ── Python parsers ──────────────────────────── */

  function parseImports(src, path) {
    var out = [];
    var lines = src.split("\n");
    for (var i = 0; i < lines.length; i++) {
      var l = lines[i].trim();
      if (l.charAt(0) === "#") continue;
      var m = l.match(/^from\s+([\w.]+)\s+import/);
      if (m) { out.push({ mod: m[1], line: i + 1, file: path }); continue; }
      m = l.match(/^import\s+([\w.]+)/);
      if (m) out.push({ mod: m[1], line: i + 1, file: path });
    }
    return out;
  }

  function parseFunctions(src, path) {
    var out = [];
    var lines = src.split("\n");
    for (var i = 0; i < lines.length; i++) {
      var m = lines[i].match(/^(\s*)(?:async\s+)?def\s+(\w+)\s*\(/);
      if (m) out.push({ name: m[2], line: i + 1, file: path, indent: m[1].length });
    }
    return out;
  }

  /* ── Analysis engine ─────────────────────────── */

  function analyze(files) {
    var allImports = [], allFuncs = [];
    var j;
    for (j = 0; j < files.length; j++) {
      allImports = allImports.concat(parseImports(files[j].content, files[j].path));
      allFuncs = allFuncs.concat(parseFunctions(files[j].content, files[j].path));
    }

    var findings = [];

    /* Signal 1: Duplicate function names across files (MDS) */
    var byName = {};
    for (j = 0; j < allFuncs.length; j++) {
      var fn = allFuncs[j];
      if (fn.name.charAt(0) === "_") continue;
      if (fn.name.indexOf("test") === 0) continue;
      if (COMMON_FN.indexOf(fn.name) >= 0) continue;
      if (!byName[fn.name]) byName[fn.name] = [];
      byName[fn.name].push(fn);
    }
    var names = Object.keys(byName);
    for (j = 0; j < names.length; j++) {
      var locs = byName[names[j]];
      var uFiles = [], seen = {};
      for (var k = 0; k < locs.length; k++) {
        if (!seen[locs[k].file]) { seen[locs[k].file] = true; uFiles.push(locs[k].file); }
      }
      if (uFiles.length < 2) continue;
      findings.push({
        signal_abbrev: "MDS", signal: "mutant_duplicates",
        severity: uFiles.length >= 3 ? "high" : "medium",
        impact: Math.min(0.3 + uFiles.length * 0.15, 0.9),
        title: "'" + names[j] + "()' defined in " + uFiles.length + " different files",
        file: locs[0].file, start_line: locs[0].line,
        next_step: "Check whether these are intentional variants or near-duplicates: " +
          uFiles.slice(0, 3).join(", ") + (uFiles.length > 3 ? " (+" + (uFiles.length - 3) + " more)" : "")
      });
    }

    /* Signal 2: Circular imports — direct A\u2194B (CIR) */
    var modOf = {};
    for (j = 0; j < files.length; j++) {
      modOf[files[j].path] = files[j].path
        .replace(/\.py$/, "").replace(/\/__init__/, "")
        .replace(/\//g, ".").replace(/^src\./, "");
    }
    var fileOf = {};
    var modKeys = Object.keys(modOf);
    for (j = 0; j < modKeys.length; j++) fileOf[modOf[modKeys[j]]] = modKeys[j];
    var mods = Object.keys(fileOf);

    var edges = {};
    for (j = 0; j < allImports.length; j++) {
      var imp = allImports[j];
      var from = modOf[imp.file];
      if (!from) continue;
      var to = imp.mod;
      var isInternal = false;
      for (var mi = 0; mi < mods.length; mi++) {
        if (mods[mi] === to || mods[mi].indexOf(to + ".") === 0 || to.indexOf(mods[mi] + ".") === 0) {
          isInternal = true; break;
        }
      }
      if (!isInternal) continue;
      if (!edges[from]) edges[from] = {};
      edges[from][to] = imp.line;
    }

    var cycleSeen = {};
    var edgeKeys = Object.keys(edges);
    for (j = 0; j < edgeKeys.length; j++) {
      var a = edgeKeys[j];
      var aTargets = Object.keys(edges[a]);
      for (var bi = 0; bi < aTargets.length; bi++) {
        var b = aTargets[bi];
        if (!edges[b]) continue;
        var bTargets = Object.keys(edges[b]);
        for (var ci = 0; ci < bTargets.length; ci++) {
          var c = bTargets[ci];
          if (c === a || a.indexOf(c + ".") === 0 || c.indexOf(a + ".") === 0) {
            var ckey = [a, b].sort().join("|");
            if (cycleSeen[ckey]) continue;
            cycleSeen[ckey] = true;
            findings.push({
              signal_abbrev: "CIR", signal: "circular_import",
              severity: "high", impact: 0.75,
              title: "Circular import: " + a.split(".").pop() + " \u2194 " + b.split(".").pop(),
              file: fileOf[a] || a, start_line: edges[a][b],
              next_step: "Break the cycle by extracting shared types into a separate module"
            });
          }
        }
      }
    }

    /* Signal 3: Large files (GCD) */
    for (j = 0; j < files.length; j++) {
      if (files[j].lineCount > 400) {
        findings.push({
          signal_abbrev: "GCD", signal: "god_class",
          severity: files[j].lineCount > 800 ? "high" : "medium",
          impact: Math.min(0.2 + files[j].lineCount / 2000, 0.8),
          title: files[j].path.split("/").pop() + " \u2014 " + files[j].lineCount + " lines",
          file: files[j].path, start_line: 1,
          next_step: "Consider splitting into smaller, focused modules"
        });
      }
    }

    /* Signal 4: God modules — many functions (GCD) */
    var fPerFile = {};
    for (j = 0; j < allFuncs.length; j++) fPerFile[allFuncs[j].file] = (fPerFile[allFuncs[j].file] || 0) + 1;
    var fpKeys = Object.keys(fPerFile);
    for (j = 0; j < fpKeys.length; j++) {
      var cnt = fPerFile[fpKeys[j]];
      if (cnt > 15) {
        findings.push({
          signal_abbrev: "GCD", signal: "god_class",
          severity: cnt > 25 ? "high" : "medium",
          impact: Math.min(0.2 + cnt / 40, 0.75),
          title: fpKeys[j].split("/").pop() + " \u2014 " + cnt + " functions in one file",
          file: fpKeys[j], start_line: 1,
          next_step: "Split into smaller modules with clear responsibilities"
        });
      }
    }

    /* Signal 5: High import fan-out (EDS) */
    var impPerFile = {};
    for (j = 0; j < allImports.length; j++) {
      if (!impPerFile[allImports[j].file]) impPerFile[allImports[j].file] = {};
      impPerFile[allImports[j].file][allImports[j].mod] = true;
    }
    var ipKeys = Object.keys(impPerFile);
    for (j = 0; j < ipKeys.length; j++) {
      var ic = Object.keys(impPerFile[ipKeys[j]]).length;
      if (ic > 15) {
        findings.push({
          signal_abbrev: "EDS", signal: "explainability_deficit",
          severity: ic > 25 ? "high" : "medium",
          impact: Math.min(0.15 + ic / 50, 0.7),
          title: ipKeys[j].split("/").pop() + " imports " + ic + " different modules",
          file: ipKeys[j], start_line: 1,
          next_step: "High import count may indicate too many responsibilities"
        });
      }
    }

    /* Sort: high severity first, then by impact */
    var sevOrd = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
    findings.sort(function (a2, b2) {
      var d = (sevOrd[a2.severity] || 4) - (sevOrd[b2.severity] || 4);
      return d !== 0 ? d : (b2.impact || 0) - (a2.impact || 0);
    });
    for (j = 0; j < findings.length; j++) findings[j].rank = j + 1;

    return { findings: findings, stats: { total_files: files.length, total_functions: allFuncs.length } };
  }

  /* ── Convert to drift-compatible JSON ──────── */

  function toDriftJson(result, analyzed, total, repoSlug) {
    var f = result.findings;
    var hi = 0, cr = 0;
    for (var i = 0; i < f.length; i++) {
      if (f[i].severity === "high") hi++;
      if (f[i].severity === "critical") cr++;
    }
    var score = Math.min(cr * 0.15 + hi * 0.08 + (f.length - hi - cr) * 0.03, 0.95);
    score = Math.round(score * 1000) / 1000;
    var sev = score > 0.7 ? "critical" : score > 0.5 ? "high"
      : score > 0.3 ? "medium" : score > 0.1 ? "low" : "info";

    return {
      schema_version: "1.0", drift_score: score, severity: sev,
      compact_summary: {
        findings_total: f.length, findings_deduplicated: f.length,
        duplicate_findings_removed: 0, critical_count: cr, high_count: hi,
        fix_first_count: Math.min(f.length, 10)
      },
      summary: { total_files: result.stats.total_files, total_functions: result.stats.total_functions },
      fix_first: f.slice(0, 10),
      findings_compact: f.slice(0, 20),
      _preview: true,
      _analyzed_files: analyzed,
      _total_python_files: total,
      _repo: repoSlug
    };
  }

  /* ── Renderers (shared for all flows) ──────── */

  function renderScore(data) {
    var sev = (data.severity || "info").toLowerCase();
    var col = SEV_COLOR[sev] || SEV_COLOR.info;
    var badge = el("div", "drift-prove-score");
    badge.style.borderColor = col;
    var num = el("span", "drift-prove-score-num", fmtScore(data.drift_score));
    num.style.color = col;
    badge.appendChild(num);
    badge.appendChild(el("span", "drift-prove-score-label", (SEV_LABEL[sev] || sev) + " severity"));

    if (data.trend && typeof data.trend.delta === "number") {
      var arrow = data.trend.delta <= 0 ? " \u25BC " : " \u25B2 ";
      var dir = data.trend.direction || (data.trend.delta <= 0 ? "improving" : "degrading");
      var t = el("span", "drift-prove-score-trend");
      t.textContent = arrow + Math.abs(data.trend.delta).toFixed(3) + " " + dir;
      t.style.color = data.trend.delta <= 0 ? "#22c55e" : "#ef4444";
      badge.appendChild(t);
    }
    return badge;
  }

  function renderSummary(data) {
    var s = data.summary || {}, cs = data.compact_summary || {};
    var p = [];
    if (s.total_files) p.push(s.total_files + " files");
    if (s.total_functions) p.push(s.total_functions + " functions");
    if (cs.findings_deduplicated != null) p.push(cs.findings_deduplicated + " findings");
    else if (cs.findings_total != null) p.push(cs.findings_total + " findings");
    if (cs.high_count) p.push(cs.high_count + " high");
    if (cs.critical_count) p.push(cs.critical_count + " critical");
    return el("div", "drift-prove-summary", p.join(" \u00B7 "));
  }

  function renderFinding(item) {
    var card = el("div", "drift-prove-finding");
    var sev = (item.severity || "info").toLowerCase();
    var pill = el("span", "drift-prove-severity", SEV_LABEL[sev] || sev);
    pill.style.background = SEV_COLOR[sev] || SEV_COLOR.info;
    card.appendChild(pill);
    card.appendChild(el("span", "drift-prove-signal", item.signal_abbrev || ""));
    card.appendChild(el("div", "drift-prove-finding-title", item.title || "(untitled)"));
    if (item.file) {
      var loc = item.file;
      if (item.start_line) loc += ":" + item.start_line;
      card.appendChild(el("div", "drift-prove-finding-file", loc));
    }
    var step = item.next_step || item.description;
    if (step) card.appendChild(el("div", "drift-prove-finding-next", step));
    return card;
  }

  function renderResults(container, data, max) {
    container.innerHTML = "";

    /* Preview banner for browser analysis */
    if (data._preview) {
      var banner = el("div", "drift-prove-preview-banner");
      banner.appendChild(el("span", null,
        "Browser preview \u2014 " + data._analyzed_files + " of " + data._total_python_files +
        " Python files analyzed via GitHub API."));
      var cta = el("span", "drift-prove-preview-cta");
      cta.textContent = " For the full 23-signal analysis: ";
      var code = el("code", null, "uvx drift-analyzer analyze --repo .");
      cta.appendChild(code);
      banner.appendChild(cta);
      container.appendChild(banner);
    }

    /* Header: score + summary */
    var header = el("div", "drift-prove-header");
    header.appendChild(renderScore(data));
    header.appendChild(renderSummary(data));
    container.appendChild(header);

    /* Findings */
    var findings = (Array.isArray(data.fix_first) && data.fix_first.length > 0
      ? data.fix_first : data.findings_compact || []).slice(0, max);
    if (findings.length > 0) {
      container.appendChild(el("div", "drift-prove-list-label", "Fix first \u2014 highest-impact findings:"));
      var list = el("div", "drift-prove-list");
      for (var i = 0; i < findings.length; i++) list.appendChild(renderFinding(findings[i]));
      container.appendChild(list);
    } else {
      container.appendChild(el("div", "drift-prove-empty",
        "No findings detected. The repo may be small, well-structured, or the analyzed subset didn\u2019t surface issues."));
    }

    /* Metadata */
    if (data.version || data.analyzed_at) {
      var parts = [];
      if (data.version) parts.push("drift v" + data.version);
      if (data.analyzed_at) { try { parts.push(new Date(data.analyzed_at).toLocaleString()); } catch (e) { /* skip */ } }
      if (data.summary && data.summary.analysis_duration_seconds)
        parts.push(data.summary.analysis_duration_seconds.toFixed(1) + "s");
      container.appendChild(el("div", "drift-prove-meta", parts.join(" \u00B7 ")));
    }

    /* Reset button */
    var btn = el("button", "drift-prove-reset", "\u21BB Reset");
    container.appendChild(btn);
    container.hidden = false;
    return btn;
  }

  function renderError(container, msg) {
    container.innerHTML = "";
    container.appendChild(el("div", "drift-prove-error", msg));
    container.hidden = false;
  }

  /* ── Flow A: Repo URL Analyzer ─────────────── */

  var ERROR_MSG = {
    RATE_LIMIT: "GitHub API rate limit reached (60 requests/hour for unauthenticated users). Try again in a few minutes.",
    NOT_FOUND: "Repository not found. Check the URL and ensure it\u2019s public.",
    ACCESS_DENIED: "Access denied. The repository may be private \u2014 only public repos are supported.",
    EMPTY_TREE: "Could not read the repository file tree."
  };

  function analyzeRepo(url, resultsEl, progressEl, formEl, max) {
    var info = parseRepoUrl(url);
    if (!info) {
      renderError(resultsEl, "Invalid GitHub URL. Use: https://github.com/owner/repo");
      return;
    }

    resultsEl.innerHTML = "";
    resultsEl.hidden = true;
    progressEl.hidden = false;

    var statusEl = progressEl.querySelector(".drift-prove-status");
    function setStatus(txt) { if (statusEl) statusEl.textContent = txt; }

    setStatus("Fetching repository info\u2026");

    ghGet("/repos/" + info.owner + "/" + info.repo)
      .then(function (repo) {
        var branch = repo.default_branch || "main";
        setStatus("Loading file tree\u2026");
        return ghGet("/repos/" + info.owner + "/" + info.repo + "/git/trees/" + branch + "?recursive=1");
      })
      .then(function (tree) {
        if (!tree.tree) throw new Error("EMPTY_TREE");

        var allPy = tree.tree.filter(function (n) { return n.type === "blob" && n.path.endsWith(".py"); });
        var totalPy = allPy.length;

        if (totalPy === 0) {
          progressEl.hidden = true;
          renderError(resultsEl, "No Python files found. Drift analyzes Python codebases.");
          throw new Error("__HANDLED__");
        }

        var selected = selectPyFiles(tree.tree);
        setStatus("Found " + totalPy + " Python files. Analyzing " + selected.length + "\u2026");

        return fetchContents(info.owner, info.repo, selected, setStatus)
          .then(function (files) {
            setStatus("Analyzing code patterns\u2026");
            var result = analyze(files);
            var driftJson = toDriftJson(result, files.length, totalPy, info.owner + "/" + info.repo);

            progressEl.hidden = true;
            var resetBtn = renderResults(resultsEl, driftJson, max);
            formEl.hidden = true;

            resetBtn.addEventListener("click", function () {
              resultsEl.innerHTML = "";
              resultsEl.hidden = true;
              formEl.hidden = false;
            });
          });
      })
      .catch(function (err) {
        if (err.message === "__HANDLED__") return;
        progressEl.hidden = true;
        renderError(resultsEl, ERROR_MSG[err.message] || "Error: " + err.message);
      });
  }

  /* ── Flow B: File Drop (secondary) ─────────── */

  function processFile(text, resultsEl, dropEl, max) {
    var data;
    try { data = JSON.parse(text); } catch (e) {
      renderError(resultsEl, "Could not parse JSON.");
      return;
    }
    if (typeof data !== "object" || data === null) {
      renderError(resultsEl, "Invalid JSON: not an object.");
      return;
    }
    if (!data.drift_score && data.drift_score !== 0) {
      renderError(resultsEl, 'Missing required field: "drift_score".');
      return;
    }
    if (!data.compact_summary) {
      renderError(resultsEl, 'Missing required field: "compact_summary".');
      return;
    }
    if (!Array.isArray(data.fix_first) && !Array.isArray(data.findings_compact)) {
      renderError(resultsEl, 'Missing required field: "fix_first" or "findings_compact".');
      return;
    }

    var resetBtn = renderResults(resultsEl, data, max);
    dropEl.hidden = true;
    resetBtn.addEventListener("click", function () {
      resultsEl.innerHTML = "";
      resultsEl.hidden = true;
      dropEl.hidden = false;
    });
  }

  function initDropZone(dropEl, resultsEl, max) {
    dropEl.addEventListener("dragover", function (e) { e.preventDefault(); dropEl.classList.add("drag-active"); });
    dropEl.addEventListener("dragleave", function (e) { e.preventDefault(); dropEl.classList.remove("drag-active"); });
    dropEl.addEventListener("drop", function (e) {
      e.preventDefault();
      dropEl.classList.remove("drag-active");
      var files = e.dataTransfer && e.dataTransfer.files;
      if (!files || !files.length) return;
      if (files[0].size > 10 * 1024 * 1024) {
        renderError(resultsEl, "File too large. Use --compact for smaller output.");
        return;
      }
      var r = new FileReader();
      r.onload = function (ev) { processFile(ev.target.result, resultsEl, dropEl, max); };
      r.readAsText(files[0]);
    });

    var pasteBtn = dropEl.querySelector("[data-prove-paste]");
    if (pasteBtn && navigator.clipboard && navigator.clipboard.readText) {
      pasteBtn.addEventListener("click", function () {
        navigator.clipboard.readText()
          .then(function (t) { if (t && t.trim()) processFile(t.trim(), resultsEl, dropEl, max); })
          .catch(function () { renderError(resultsEl, "Clipboard unavailable. Drop the file instead."); });
      });
    } else if (pasteBtn) {
      pasteBtn.style.display = "none";
    }

    var fileInput = dropEl.querySelector("[data-prove-file]");
    if (fileInput) {
      fileInput.addEventListener("change", function () {
        if (!fileInput.files || !fileInput.files[0]) return;
        var r = new FileReader();
        r.onload = function (ev) { processFile(ev.target.result, resultsEl, dropEl, max); };
        r.readAsText(fileInput.files[0]);
      });
    }
  }

  /* ── Initialization ──────────────────────────── */

  function init() {
    /* Flow A: Repo URL forms */
    var forms = document.querySelectorAll(".drift-prove-form");
    for (var i = 0; i < forms.length; i++) {
      (function (form) {
        var max = parseInt(form.getAttribute("data-max-findings") || "5", 10);
        var targetId = form.getAttribute("data-results-target");
        var results = targetId
          ? document.getElementById(targetId)
          : form.parentElement.querySelector(".drift-prove-results");
        var progress = form.parentElement.querySelector(".drift-prove-progress");

        if (!results) return;

        form.addEventListener("submit", function (e) {
          e.preventDefault();
          var input = form.querySelector(".drift-prove-url");
          if (input && input.value.trim()) {
            analyzeRepo(input.value, results, progress, form, max);
          }
        });
      })(forms[i]);
    }

    /* Flow B: Drop zones */
    var drops = document.querySelectorAll(".drift-prove-drop");
    for (var d = 0; d < drops.length; d++) {
      var drop = drops[d];
      var maxD = parseInt(drop.getAttribute("data-max-findings") || "5", 10);
      var targetD = drop.getAttribute("data-results-target");
      var resultsD = targetD
        ? document.getElementById(targetD)
        : drop.parentElement.querySelector(".drift-prove-results");
      if (resultsD) initDropZone(drop, resultsD, maxD);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
