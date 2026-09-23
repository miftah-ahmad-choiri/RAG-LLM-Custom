/* app.js — Client-side logic for the IBM Ceph Docs Scraper (Excel-driven) */

(() => {
  'use strict';

  // ── Element refs ────────────────────────────────────────────────────────────
  const excelSelect    = document.getElementById('excel-select');
  const sourceStats    = document.getElementById('source-stats');
  const statTotal      = document.getElementById('stat-total');
  const statSections   = document.getElementById('stat-sections');
  const noExcel        = document.getElementById('no-excel');
  const sectionsCard   = document.getElementById('sections-card');
  const sectionList    = document.getElementById('section-list');

  const btnStart       = document.getElementById('btn-start');
  const btnStop        = document.getElementById('btn-stop');
  const btnDownload    = document.getElementById('btn-download');
  const btnNewJob      = document.getElementById('btn-new-job');
  const btnClearLog    = document.getElementById('btn-clear-log');
  const btnDownloadPartial = document.getElementById('btn-download-partial');

  const progressCard   = document.getElementById('progress-card');
  const partialCard    = document.getElementById('partial-card');
  const partialDir     = document.getElementById('partial-dir');
  const resultCard     = document.getElementById('result-card');
  const errorCard      = document.getElementById('error-card');
  const logCard        = document.getElementById('log-card');
  const jobsCard       = document.getElementById('jobs-card');

  const progressLabel  = document.getElementById('progress-label');
  const progressPct    = document.getElementById('progress-pct');
  const progressFill   = document.getElementById('progress-fill');
  const currentUrl     = document.getElementById('current-url');
  const logTerminal    = document.getElementById('log-terminal');
  const resultMeta     = document.getElementById('result-meta');
  const errorMsg       = document.getElementById('error-msg');
  const jobsList       = document.getElementById('jobs-list');
  const rateLimit      = document.getElementById('rate-limit');

  const scanCard       = document.getElementById('scan-card');
  const scanSessionDir = document.getElementById('scan-session-dir');
  const btnScan        = document.getElementById('btn-scan');
  const scanResults    = document.getElementById('scan-results');
  const scanCleanCount = document.getElementById('scan-clean-count');
  const scanFailedCount = document.getElementById('scan-failed-count');
  const resumeActionsRow = document.getElementById('resume-actions-row');
  const btnResume      = document.getElementById('btn-resume');

  let detectedSessionDir = null;

  const fcTotal        = document.getElementById('fc-total');
  const fcOk           = document.getElementById('fc-ok');
  const fcErr          = document.getElementById('fc-err');

  let currentJobId = null;
  let pollTimer    = null;
  let loggedLines  = new Set();

  // ── Utilities ────────────────────────────────────────────────────────────────
  const show = el => el.classList.remove('hidden');
  const hide = el => el.classList.add('hidden');

  function colorLine(line) {
    if (line.includes('✅') || line.includes('Done'))       return 'log-line-ok';
    if (line.includes('❌') || line.includes('💥'))         return 'log-line-err';
    if (line.includes('📂') || line.includes('📁') || line.includes('🔗')) return 'log-line-info';
    if (line.includes('⚠️') || line.includes('🛑'))         return 'log-line-warn';
    return '';
  }

  function appendLog(lines) {
    lines.forEach(line => {
      if (loggedLines.has(line)) return;
      loggedLines.add(line);
      const span = document.createElement('span');
      const cls = colorLine(line);
      if (cls) span.className = cls;
      span.textContent = line + '\n';
      logTerminal.appendChild(span);
    });
    logTerminal.scrollTop = logTerminal.scrollHeight;
  }

  function statusBadge(status) {
    return `<span class="job-status status-${status}">${status}</span>`;
  }

  function fmtSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  // ── Load Excel file list on page load ────────────────────────────────────────
  async function loadExcelFiles() {
    try {
      const resp  = await fetch('/api/excel-files');
      const files = await resp.json();

      if (!files.length) {
        excelSelect.style.display = 'none';
        noExcel.style.display = '';
        btnStart.disabled = true;
        return;
      }

      noExcel.style.display = 'none';
      excelSelect.innerHTML = files.map(f =>
        `<option value="${f.name}">${f.name}  (${f.mtime})</option>`
      ).join('');

      // Auto-load info for the first (newest) file
      await loadExcelInfo(files[0].name);
    } catch (e) {
      excelSelect.innerHTML = '<option value="">Failed to load files</option>';
      console.error('loadExcelFiles:', e);
    }
  }

  async function loadExcelInfo(filename) {
    if (!filename) return;
    try {
      const resp = await fetch(`/api/excel-info?file=${encodeURIComponent(filename)}`);
      const data = await resp.json();
      if (data.error) { console.warn(data.error); return; }

      statTotal.textContent    = `${data.total.toLocaleString()} URLs`;
      statSections.textContent = `${data.section_count} sections`;
      sourceStats.style.display = '';

      // Populate section list
      sectionList.innerHTML = data.sections.map(s =>
        `<li>
          <span class="s-idx">${s.index}</span>
          <span class="s-name" title="${s.description}">${s.description}</span>
          <span class="s-cnt">${s.entry_count}</span>
        </li>`
      ).join('');
      sectionsCard.style.display = '';

      btnStart.disabled = false;
      
      // Auto-detect existing session for this file
      await detectExistingSession(filename);
    } catch (e) {
      console.error('loadExcelInfo:', e);
    }
  }

  async function detectExistingSession(filename) {
    if (!filename) return;
    hide(scanCard);
    hide(scanResults);
    hide(resumeActionsRow);
    detectedSessionDir = null;

    try {
      const resp = await fetch(`/api/detect-session/${encodeURIComponent(filename)}`);
      const data = await resp.json();
      if (data.session_dir) {
        detectedSessionDir = data.session_dir;
        scanSessionDir.textContent = `output/md/${data.session_dir}/`;
        show(scanCard);
      }
    } catch (e) {
      console.error('detectExistingSession:', e);
    }
  }

  excelSelect.addEventListener('change', () => {
    loadExcelInfo(excelSelect.value);
    btnStart.disabled = !excelSelect.value;
  });

  // ── Start job ────────────────────────────────────────────────────────────────
  btnStart.addEventListener('click', async () => {
    const excelFile = excelSelect.value;
    if (!excelFile) { alert('Please select an Excel file first.'); return; }

    // Reset UI state
    loggedLines.clear();
    logTerminal.innerHTML = '';
    hide(resultCard);
    hide(partialCard);
    hide(errorCard);
    show(progressCard);
    show(logCard);
    btnStart.disabled = true;
    show(btnStop);

    progressFill.style.width  = '0%';
    progressLabel.textContent = 'Starting…';
    progressPct.textContent   = '0%';
    currentUrl.textContent    = '–';
    fcTotal.textContent = '0';
    fcOk.textContent    = '✓ 0';
    fcErr.textContent   = '✗ 0';

    try {
      const resp = await fetch('/api/start', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          excel_file: excelFile,
          rate_limit: parseFloat(rateLimit.value),
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'Failed to start job');

      currentJobId = data.job_id;
      appendLog([`🚀 Job ${currentJobId} started — scraping ${excelFile}`]);
      startPolling();
    } catch (err) {
      showError(err.message);
      btnStart.disabled = false;
      hide(btnStop);
    }
  });

  // ── Stop ─────────────────────────────────────────────────────────────────────
  btnStop.addEventListener('click', async () => {
    if (!currentJobId) return;
    btnStop.disabled = true;
    btnStop.textContent = 'Stopping…';
    await fetch(`/api/cancel/${currentJobId}`, { method: 'POST' });
    appendLog(['🛑 Stop requested — waiting for current page to finish…']);
  });

  // ── Scan Existing Folder ─────────────────────────────────────────────────────
  btnScan.addEventListener('click', async () => {
    const excelFile = excelSelect.value;
    if (!excelFile || !detectedSessionDir) return;

    btnScan.disabled = true;
    btnScan.textContent = 'Scanning…';
    hide(scanResults);
    hide(resumeActionsRow);

    try {
      const resp = await fetch('/api/scan-status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          excel_file: excelFile,
          session_dir: detectedSessionDir
        })
      });
      const data = await resp.json();
      if (data.error) { alert(data.error); return; }

      scanCleanCount.textContent = data.clean.toLocaleString();
      scanFailedCount.textContent = data.failed.toLocaleString();
      show(scanResults);

      if (data.failed > 0) {
        show(resumeActionsRow);
      } else {
        hide(resumeActionsRow);
        appendLog(['🎉 Scan complete: All files are already clean! Nothing to resume.']);
      }
    } catch (e) {
      console.error('btnScan:', e);
    } finally {
      btnScan.disabled = false;
      btnScan.textContent = 'Scan Folder Status';
    }
  });

  // ── Resume Scraping Remaining ────────────────────────────────────────────────
  btnResume.addEventListener('click', async () => {
    const excelFile = excelSelect.value;
    if (!excelFile || !detectedSessionDir) return;

    // Reset UI state
    loggedLines.clear();
    logTerminal.innerHTML = '';
    hide(resultCard);
    hide(partialCard);
    hide(errorCard);
    show(progressCard);
    show(logCard);
    btnStart.disabled = true;
    btnResume.disabled = true;
    show(btnStop);

    progressFill.style.width  = '0%';
    progressLabel.textContent = 'Starting…';
    progressPct.textContent   = '0%';
    currentUrl.textContent    = '–';
    fcTotal.textContent = '0';
    fcOk.textContent    = '✓ 0';
    fcErr.textContent   = '✗ 0';

    try {
      const resp = await fetch('/api/start', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          excel_file: excelFile,
          session_dir: detectedSessionDir,
          resume: true,
          rate_limit: parseFloat(rateLimit.value),
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'Failed to start job');

      currentJobId = data.job_id;
      appendLog([`🚀 Job ${currentJobId} started (Resuming session: ${detectedSessionDir})`]);
      startPolling();
    } catch (err) {
      showError(err.message);
      btnStart.disabled = false;
      btnResume.disabled = false;
      hide(btnStop);
    } finally {
      btnResume.disabled = false;
    }
  });

  // ── Polling ──────────────────────────────────────────────────────────────────
  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(pollStatus, 1500);
  }

  function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  }

  async function pollStatus() {
    if (!currentJobId) return;
    try {
      const resp = await fetch(`/api/status/${currentJobId}`);
      if (!resp.ok) return;
      const job = await resp.json();

      // Progress bar
      const pct = job.total > 0 ? Math.round((job.progress / job.total) * 100) : 0;
      progressFill.style.width  = `${pct}%`;
      progressLabel.textContent = `${job.progress.toLocaleString()} / ${job.total.toLocaleString()} pages`;
      progressPct.textContent   = `${pct}%`;
      if (job.current_url) currentUrl.textContent = job.current_url;

      // File counters
      fcTotal.textContent = job.files_created.toLocaleString();
      fcOk.textContent    = `✓ ${job.files_ok.toLocaleString()}`;
      fcErr.textContent   = `✗ ${job.files_failed.toLocaleString()}`;

      // Log lines
      if (job.log && job.log.length) appendLog(job.log);

      // Partial download (output_dir set after session folder is created)
      if (job.output_dir && job.status === 'running') {
        partialDir.textContent = `output/md/${job.output_dir}/`;
        show(partialCard);
        btnDownloadPartial.onclick = () => {
          window.location.href = `/api/download/${job.id}`;
        };
      }

      if (job.status === 'done') {
        stopPolling();
        hide(partialCard);
        progressFill.style.width  = '100%';
        progressLabel.textContent = `${job.total.toLocaleString()} / ${job.total.toLocaleString()} pages`;
        progressPct.textContent   = '100%';
        showResult(job);
        refreshJobHistory();
      } else if (job.status === 'error') {
        stopPolling();
        showError(job.error || 'Unknown error');
        btnStart.disabled = false;
        hide(btnStop);
        refreshJobHistory();
      } else if (job.status === 'cancelled') {
        stopPolling();
        hide(btnStop);
        btnStop.disabled = false;
        btnStop.textContent = '⏹ Stop';
        appendLog(['🛑 Stopped — files already scraped are preserved.']);
        btnStart.disabled = false;
        refreshJobHistory();
        // Show the scan card for the stopped session so the user can resume
        if (job.output_dir) {
          detectedSessionDir = job.output_dir;
          scanSessionDir.textContent = `output/md/${job.output_dir}/`;
          show(scanCard);
          hide(scanResults);
          hide(resumeActionsRow);
          // Auto-trigger a scan so the user sees exactly what's left
          autoScanAfterStop(job.output_dir);
        }
      }
    } catch (err) {
      console.error('Poll error:', err);
    }
  }

  // ── Auto-scan after stop ─────────────────────────────────────────────────────
  async function autoScanAfterStop(sessionDir) {
    const excelFile = excelSelect.value;
    if (!excelFile || !sessionDir) return;
    try {
      const resp = await fetch('/api/scan-status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ excel_file: excelFile, session_dir: sessionDir })
      });
      const data = await resp.json();
      if (data.error) return;
      scanCleanCount.textContent = data.clean.toLocaleString();
      scanFailedCount.textContent = data.failed.toLocaleString();
      show(scanResults);
      if (data.failed > 0) {
        show(resumeActionsRow);
        appendLog([`📊 ${data.clean} pages saved, ${data.failed} still need scraping — click "Resume Failed Scrapes Only" to continue.`]);
      } else {
        appendLog(['🎉 All pages were successfully scraped before stopping!']);
      }
    } catch (e) {
      console.error('autoScanAfterStop:', e);
    }
  }

  // ── Show result ──────────────────────────────────────────────────────────────
  function showResult(job) {
    hide(btnStop);
    btnStop.disabled = false;
    btnStop.textContent = '⏹ Stop';
    btnStart.disabled = false;
    show(resultCard);

    resultMeta.innerHTML = `
      <strong>📁 Output folder:</strong> <code>output/md/${job.output_dir}/</code><br>
      <strong>📄 Files written:</strong> ${job.files_ok.toLocaleString()} ok,
        ${job.files_failed > 0
          ? `<span style="color:var(--danger)">${job.files_failed} failed</span>`
          : '0 failed'
        }<br>
      <strong>🔗 Pages processed:</strong> ${job.total.toLocaleString()}
    `;

    btnDownload.onclick = () => {
      window.location.href = `/api/download/${job.id}`;
    };
  }

  // ── Show error ───────────────────────────────────────────────────────────────
  function showError(msg) {
    show(errorCard);
    errorMsg.textContent = msg;
  }

  // ── New job ──────────────────────────────────────────────────────────────────
  btnNewJob.addEventListener('click', async () => {
    currentJobId = null;
    loggedLines.clear();
    logTerminal.innerHTML = '';
    hide(resultCard);
    hide(partialCard);
    hide(errorCard);
    hide(progressCard);
    hide(logCard);
    hide(scanCard);
    hide(scanResults);
    hide(resumeActionsRow);
    progressFill.style.width = '0%';
    btnStop.disabled = false;
    btnStop.textContent = '⏹ Stop';
    btnStart.disabled = false;
    // Reload info for currently selected file to trigger session auto-detection
    await loadExcelInfo(excelSelect.value);
  });

  // ── Clear log ────────────────────────────────────────────────────────────────
  btnClearLog.addEventListener('click', () => {
    logTerminal.innerHTML = '';
    loggedLines.clear();
  });

  // ── Job history ──────────────────────────────────────────────────────────────
  async function refreshJobHistory() {
    try {
      const resp = await fetch('/api/jobs');
      const jobs = await resp.json();

      if (!jobs.length) {
        jobsList.innerHTML = '<span class="muted">No jobs yet.</span>';
        return;
      }

      jobsList.innerHTML = jobs.map(j => `
        <div class="job-row">
          <span class="job-id">#${j.id}</span>
          ${statusBadge(j.status)}
          <span class="muted" style="flex:1;font-size:11.5px;">
            ${j.total > 0
              ? `${j.progress.toLocaleString()}/${j.total.toLocaleString()} pages · ${j.files_created.toLocaleString()} files`
              : '–'}
          </span>
          <div class="job-actions">
            ${j.status === 'done' || (j.status === 'running' && j.output_dir)
              ? `<button class="btn btn-secondary" style="padding:3px 10px;font-size:11.5px"
                   onclick="window.location='/api/download/${j.id}'">⬇ .zip</button>`
              : ''}
          </div>
        </div>
      `).join('');
    } catch (e) {
      console.error('Jobs history error:', e);
    }
  }

  // ── Init ─────────────────────────────────────────────────────────────────────
  loadExcelFiles();
  refreshJobHistory();
  setInterval(refreshJobHistory, 10000);

})();
