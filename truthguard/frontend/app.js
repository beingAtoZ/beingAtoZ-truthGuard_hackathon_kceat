/* ── CONFIG ── */
const API_BASE = 'http://localhost:8000/api';

/* ── STATE ── */
let currentTab = 'text';
let selectedFile = null;

/* ── TAB SWITCHING ── */
function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.toggle('active', b.id === `tab-${tab}`);
    b.setAttribute('aria-selected', b.id === `tab-${tab}`);
  });
  document.querySelectorAll('.input-panel').forEach(p => p.classList.add('hidden'));
  document.getElementById(`panel-${tab}`).classList.remove('hidden');
}

/* ── DRAG & DROP ── */
function handleDragOver(e) {
  e.preventDefault();
  document.getElementById('dropzone').classList.add('drag-over');
}
function handleDrop(e) {
  e.preventDefault();
  document.getElementById('dropzone').classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file && file.type.startsWith('image/')) loadImagePreview(file);
}
function handleFileSelect(e) {
  const file = e.target.files[0];
  if (file) loadImagePreview(file);
}
function loadImagePreview(file) {
  selectedFile = file;
  const reader = new FileReader();
  reader.onload = (e) => {
    const preview = document.getElementById('imagePreview');
    preview.src = e.target.result;
    preview.classList.remove('hidden');
    document.getElementById('dropzoneContent').classList.add('hidden');
  };
  reader.readAsDataURL(file);
}

/* ── TOAST NOTIFICATION SYSTEM ── */
/**
 * Show a styled toast notification instead of alert().
 * @param {string} message
 * @param {'error'|'warning'|'info'|'success'} type
 * @param {number} duration ms (0 = persistent)
 */
function showToast(message, type = 'error', duration = 5000) {
  const container = document.getElementById('toastContainer');

  const colors = {
    error:   { bg: 'linear-gradient(135deg,#7f1d1d,#991b1b)', border: '#ef4444', icon: '❌' },
    warning: { bg: 'linear-gradient(135deg,#78350f,#92400e)', border: '#f59e0b', icon: '⚠️' },
    info:    { bg: 'linear-gradient(135deg,#1e3a5f,#1e40af)', border: '#3b82f6', icon: 'ℹ️' },
    success: { bg: 'linear-gradient(135deg,#064e3b,#065f46)', border: '#10b981', icon: '✅' },
  };
  const c = colors[type] || colors.info;

  const toast = document.createElement('div');
  toast.setAttribute('role', 'alert');
  toast.style.cssText = `
    background: ${c.bg};
    border: 1px solid ${c.border};
    border-left: 4px solid ${c.border};
    color: #f8fafc;
    padding: 0.85rem 1.1rem;
    border-radius: 10px;
    font-size: 0.875rem;
    font-weight: 500;
    max-width: 360px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
    animation: toastIn 0.3s ease;
    cursor: pointer;
    backdrop-filter: blur(8px);
    line-height: 1.4;
  `;
  toast.innerHTML = `<span style="font-size:1rem;line-height:1.4;">${c.icon}</span><span>${message}</span>`;
  toast.addEventListener('click', () => dismissToast(toast));

  if (!document.getElementById('toastKeyframes')) {
    const style = document.createElement('style');
    style.id = 'toastKeyframes';
    style.textContent = `
      @keyframes toastIn  { from { opacity:0; transform:translateX(60px); } to { opacity:1; transform:translateX(0); } }
      @keyframes toastOut { from { opacity:1; transform:translateX(0);    } to { opacity:0; transform:translateX(60px); } }
    `;
    document.head.appendChild(style);
  }

  container.appendChild(toast);

  if (duration > 0) {
    setTimeout(() => dismissToast(toast), duration);
  }
  return toast;
}

function dismissToast(toast) {
  toast.style.animation = 'toastOut 0.3s ease forwards';
  setTimeout(() => toast.remove(), 300);
}

/* Backwards-compat alias */
function showError(msg) { showToast(msg, 'error'); }

/* ── BACKEND HEALTH / OFFLINE BANNER ── */
async function checkBackendHealth() {
  try {
    const resp = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    if (resp.ok) {
      document.getElementById('offlineBanner').classList.add('hidden');
      return true;
    }
  } catch (_) { /* fall through */ }
  return false;
}

/* ── MAIN ANALYSIS ── */
async function analyzeContent() {
  let inputText = '', inputType = currentTab;

  if (currentTab === 'text') {
    inputText = document.getElementById('textInput').value.trim();
    if (!inputText) { showToast('Please enter some text to analyze.', 'warning'); return; }
  } else if (currentTab === 'url') {
    inputText = document.getElementById('urlInput').value.trim();
    if (!inputText) { showToast('Please enter a URL to analyze.', 'warning'); return; }
  } else if (currentTab === 'image') {
    if (!selectedFile) { showToast('Please select an image to analyze.', 'warning'); return; }
  }

  setLoading(true);
  hideResults();
  showProgressCard();

  const steps = [
    { id: 'extract',    label: 'Extracting and preprocessing content...' },
    { id: 'nlp',        label: 'Running NLP analysis and claim extraction...' },
    { id: 'classify',   label: 'Classifying with multi-model AI engine...' },
    { id: 'credcheck',  label: 'Scoring source credibility...' },
    { id: 'newssearch', label: 'Searching verified news channels online...' },
    { id: 'factcheck',  label: 'Cross-referencing claims with fact databases...' },
    { id: 'explain',    label: 'Generating AI explanation...' },
  ];
  animateSteps(steps);

  try {
    let result;
    let backendOnline = false;

    try {
      if (inputType === 'image') {
        const formData = new FormData();
        formData.append('file', selectedFile);
        const resp = await fetch(`${API_BASE}/analyze/image`, {
          method: 'POST', body: formData, signal: AbortSignal.timeout(20000)
        });
        if (!resp.ok) {
          const errData = await resp.json().catch(()=>({}));
          throw new Error(`HTTP_${resp.status}: ${errData.detail || 'Failed to analyze image'}`);
        }
        result = await resp.json();
      } else if (inputType === 'url') {
        const resp = await fetch(`${API_BASE}/analyze/url`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: inputText }),
          signal: AbortSignal.timeout(20000)
        });
        if (!resp.ok) {
          const errData = await resp.json().catch(()=>({}));
          throw new Error(`HTTP_${resp.status}: ${errData.detail || 'Could not analyze URL'}`);
        }
        result = await resp.json();
      } else {
        const resp = await fetch(`${API_BASE}/analyze/text`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: inputText }),
          signal: AbortSignal.timeout(20000)
        });
        if (!resp.ok) {
          const errData = await resp.json().catch(()=>({}));
          throw new Error(`HTTP_${resp.status}: ${errData.detail || 'Could not analyze text'}`);
        }
        result = await resp.json();
      }
      backendOnline = true;
      // Hide offline banner if we succeeded
      document.getElementById('offlineBanner').classList.add('hidden');

    } catch (fetchErr) {
      // If it's a known HTTP error, rethrow to be caught by the outer catch
      if (fetchErr.message.startsWith('HTTP_')) {
        throw new Error(fetchErr.message.substring(9)); // Strip 'HTTP_xxx: ' prefix
      }
      
      // Otherwise it's a network failure (Backend not running)
      console.warn('[TruthGuard] Backend unavailable:', fetchErr.message);
      document.getElementById('offlineBanner').classList.remove('hidden');
      document.getElementById('offlineBanner').style.display = 'flex';
      await new Promise(r => setTimeout(r, 2500));
      result = generateDemoResult(inputText || selectedFile?.name || '', inputType);
    }

    hideProgressCard();
    setLoading(false);
    renderResults(result, backendOnline);

  } catch (err) {
    hideProgressCard();
    setLoading(false);
    showToast('Analysis failed: ' + err.message, 'error');
  }
}

/* ── IMPROVED DEMO RESULT GENERATOR ── */
/**
 * Heuristic demo result for when backend is offline.
 * Fixes the original which returned the same "corroboration" articles for
 * everything, causing artificially high confidence for any plain text.
 * Now clearly labelled as demo/illustrative data throughout.
 */
function generateDemoResult(input, type) {
  const text = (input || '').toLowerCase();

  const fakeSignals    = ['shocking', 'breaking', 'hoax', 'fake', 'conspiracy', 'secret', "don't want you",
                          'leaked', 'banned', 'miracle', 'exposed', 'plandemic', 'chemtrail', 'microchip',
                          'deep state', 'crisis actor', 'government hiding'];
  const realSignals    = ['according to', 'study', 'research', 'scientists', 'officials said', 'reported by',
                          'confirmed', 'peer-reviewed', 'published in', 'in a statement', 'told reporters'];
  const misleadSignals = ['out of context', 'misleading', 'debated', 'disputed', 'alleged', 'reportedly', 'claims'];

  let fakeScore    = fakeSignals.filter(s => text.includes(s)).length;
  let realScore    = realSignals.filter(s => text.includes(s)).length;
  let misleadScore = misleadSignals.filter(s => text.includes(s)).length;

  // Stylistic signals
  const exclamCount = (input.match(/!/g) || []).length;
  const capsRatio   = [...input].filter(c => c >= 'A' && c <= 'Z').length / Math.max(input.length, 1);
  if (exclamCount > 3)  fakeScore++;
  if (capsRatio > 0.15) fakeScore++;

  let verdict, confidence, color;

  if (fakeScore >= 2 && fakeScore > realScore) {
    verdict    = 'FAKE';
    confidence = Math.min(94, 65 + fakeScore * 4);
    color      = 'fake';
  } else if (realScore >= 2 && realScore > fakeScore) {
    verdict    = 'REAL';
    confidence = Math.min(91, 68 + realScore * 3);
    color      = 'real';
  } else if (misleadScore >= 1 || fakeScore === 1 || (fakeScore === 1 && realScore === 1)) {
    verdict    = 'MISLEADING';
    confidence = Math.min(78, 58 + misleadScore * 5);
    color      = 'misleading';
  } else {
    verdict    = 'UNVERIFIED';
    confidence = Math.floor(Math.random() * 12) + 48; // 48–60 — appropriately uncertain
    color      = 'unverified';
  }

  const domain = type === 'url' ? extractDomain(input) : null;

  const explanations = {
    FAKE:       `[Demo] This content displays markers of misinformation: sensationalist language, unverified extraordinary claims, and absence of credible citations. Heuristic analysis detected ${fakeScore} fake-news signal(s). ⚠️ This is illustrative — start the backend for real AI analysis.`,
    REAL:       `[Demo] This content appears credible based on factual writing style and presence of verifiable attribution signals. Heuristic analysis detected ${realScore} credibility signal(s). ⚠️ This is illustrative — start the backend for real AI analysis.`,
    MISLEADING: `[Demo] This content may contain factual elements but uses framing that omits important context or is selectively presented. Heuristic analysis flagged ${misleadScore} ambiguous signal(s). ⚠️ This is illustrative — start the backend for real AI analysis.`,
    UNVERIFIED: `[Demo] Insufficient signals to classify confidently. The content does not strongly match known real or fake patterns. ⚠️ This is illustrative — start the backend for real AI analysis.`,
  };

  return {
    verdict, confidence, color,
    explanation: explanations[verdict],
    source: {
      domain: domain || 'Direct text input (demo)',
      score:  verdict === 'REAL' ? 72 : verdict === 'FAKE' ? 18 : 45,
      details: [
        domain ? `Domain: ${domain}` : 'No URL provided — demo mode',
        `Heuristic fake signals: ${fakeScore}`,
        `Heuristic real signals: ${realScore}`,
        '⚠️ Backend offline — scores are estimates only',
      ]
    },
    evidence: [
      {
        claim: 'Demo mode — no real fact-check performed',
        verdict: 'unverified',
        label: 'Not verified (demo)'
      }
    ],
    tags: [
      'Demo Mode', 'Heuristic Analysis', 'Backend Offline',
      type === 'image' ? 'Image Input' : type === 'url' ? 'URL Input' : 'Text Input'
    ],
    verified_news: {
      found: false,
      match_count: 0,
      search_query: text.substring(0, 80),
      verdict_signal: 'not_found',
      articles: [],
      api_used: 'none',
    }
  };
}

function extractDomain(url) {
  try { return new URL(url).hostname.replace('www.', ''); }
  catch { return url.substring(0, 30); }
}

/* ── RENDER RESULTS ── */
function renderResults(result, backendOnline = true) {
  const { verdict, confidence, color, explanation, source, evidence, tags } = result;

  // Verdict
  const icons = { FAKE: '❌', REAL: '✅', MISLEADING: '⚠️', UNVERIFIED: '❓' };
  const verdictIconWrap = document.getElementById('verdictIconWrap');
  verdictIconWrap.className = `verdict-icon-wrap ${color}`;
  verdictIconWrap.textContent = icons[verdict] || '🔍';

  const verdictText = document.getElementById('verdictText');
  verdictText.textContent = verdict;
  verdictText.className = `verdict-text ${color}`;

  document.getElementById('confidenceText').textContent = `${confidence}%`;

  // Ring
  const circle = document.getElementById('ringCircle');
  const circumference = 213.6;
  const offset = circumference - (confidence / 100) * circumference;
  const ringColors = { FAKE: '#ef4444', REAL: '#10b981', MISLEADING: '#f59e0b', UNVERIFIED: '#06b6d4' };
  setTimeout(() => {
    circle.style.strokeDashoffset = offset;
    circle.style.stroke = ringColors[verdict] || '#a78bfa';
  }, 200);
  document.getElementById('ringLabel').textContent = `${confidence}%`;

  // Confidence bar
  const barFill = document.getElementById('confidenceBarFill');
  const barColors = {
    FAKE:       'linear-gradient(90deg,#ef4444,#b91c1c)',
    REAL:       'linear-gradient(90deg,#10b981,#059669)',
    MISLEADING: 'linear-gradient(90deg,#f59e0b,#d97706)',
    UNVERIFIED: 'linear-gradient(90deg,#06b6d4,#0891b2)'
  };
  barFill.style.background = barColors[verdict] || 'linear-gradient(90deg,#7c3aed,#4f46e5)';
  setTimeout(() => { barFill.style.width = `${confidence}%`; }, 200);

  // Explanation
  document.getElementById('explanationText').textContent = explanation;

  // Source credibility
  document.getElementById('sourceDomain').textContent = source.domain;
  const credScore = source.score;
  const credFill  = document.getElementById('credMeterFill');
  const credColor = credScore >= 70 ? '#10b981' : credScore >= 40 ? '#f59e0b' : '#ef4444';
  credFill.style.background = credColor;
  setTimeout(() => { credFill.style.width = `${credScore}%`; }, 300);
  const credScoreEl = document.getElementById('credScore');
  credScoreEl.textContent = `${credScore}/100`;
  credScoreEl.style.color = credColor;

  const sourceDetails = document.getElementById('sourceDetails');
  sourceDetails.innerHTML = (source.details || []).map(d => `
    <div class="source-detail-item">
      <div class="detail-dot" style="background:${credColor}"></div>
      <span>${d}</span>
    </div>
  `).join('');

  // Evidence
  const evidenceList = document.getElementById('evidenceList');
  evidenceList.innerHTML = (evidence || []).map(e => `
    <div class="evidence-item">
      <div class="evidence-claim">${e.claim}</div>
      <span class="evidence-verdict ${e.verdict}">${e.label}</span>
    </div>
  `).join('');

  // Tags
  const tagsRow = document.getElementById('tagsRow');
  tagsRow.innerHTML = (tags || []).map(t => `<span class="tag">${t}</span>`).join('');

  // Verified news
  renderVerifiedNews(result.verified_news, backendOnline);

  // Show results
  document.getElementById('resultsContainer').classList.remove('hidden');
  document.getElementById('resultsContainer').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ── STEP ANIMATION ── */
function animateSteps(steps) {
  const list = document.getElementById('stepsList');
  list.innerHTML = steps.map(s => `
    <div class="step-item" id="step-${s.id}">
      <div class="step-dot"></div>
      <span>${s.label}</span>
    </div>
  `).join('');

  let i = 0;
  function next() {
    if (i > 0) {
      const prev = document.getElementById(`step-${steps[i - 1].id}`);
      if (prev) { prev.classList.remove('active'); prev.classList.add('done'); }
    }
    if (i < steps.length) {
      const cur = document.getElementById(`step-${steps[i].id}`);
      if (cur) cur.classList.add('active');
      i++;
      setTimeout(next, 420 + Math.random() * 220);
    }
  }
  next();
}

/* ── UI HELPERS ── */
function setLoading(on) {
  const btn = document.getElementById('analyzeBtn');
  btn.disabled = on;
  document.getElementById('btnText').classList.toggle('hidden', on);
  document.getElementById('btnLoading').classList.toggle('hidden', !on);
}
function showProgressCard() {
  document.getElementById('progressCard').classList.remove('hidden');
  document.getElementById('progressCard').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
function hideProgressCard() {
  document.getElementById('progressCard').classList.add('hidden');
}
function hideResults() {
  document.getElementById('resultsContainer').classList.add('hidden');
}
function resetAnalysis() {
  hideResults();
  hideProgressCard();
  document.getElementById('textInput').value = '';
  document.getElementById('urlInput').value = '';
  document.getElementById('fileInput').value = '';
  document.getElementById('imagePreview').classList.add('hidden');
  document.getElementById('dropzoneContent').classList.remove('hidden');
  selectedFile = null;
  document.getElementById('ringCircle').style.strokeDashoffset = '213.6';
  document.getElementById('confidenceBarFill').style.width = '0';
  document.getElementById('credMeterFill').style.width = '0';
  document.getElementById('analyzerCard').scrollIntoView({ behavior: 'smooth' });
}

/* ── VERIFIED NEWS RENDERER ── */
function renderVerifiedNews(news, backendOnline = true) {
  if (!news) return;

  const { found, match_count, search_query, articles, verdict_signal, api_used } = news;

  // Signal badge
  const badge = document.getElementById('newsSignalBadge');
  const signalMap = {
    corroborates: { text: '✓ Covered by trusted outlets',      cls: 'corroborates' },
    contradicts:  { text: '✗ Contradicted by trusted outlets', cls: 'contradicts' },
    not_found:    { text: '⚠ Not found in verified news',      cls: 'not_found' },
  };
  const signal = signalMap[verdict_signal] || signalMap['not_found'];
  badge.textContent = signal.text;
  badge.className = `panel-header-badge ${signal.cls}`;

  // Search query + data source transparency
  const queryEl = document.getElementById('newsSearchQuery');
  let sourceLabel = '';
  if (!backendOnline) {
    sourceLabel = ' <span style="color:#f59e0b;font-size:0.72rem;">[demo — backend offline]</span>';
  } else if (api_used && api_used !== 'none' && api_used !== 'demo') {
    sourceLabel = ` <span style="color:#6ee7b7;font-size:0.72rem;">[via ${api_used}]</span>`;
  } else if (api_used === 'demo') {
    sourceLabel = ' <span style="color:#f59e0b;font-size:0.72rem;">[illustrative — DEMO_MODE=true]</span>';
  } else {
    sourceLabel = ' <span style="color:#94a3b8;font-size:0.72rem;">[no news API configured]</span>';
  }
  queryEl.innerHTML = `Search query: "${search_query || '—'}"${sourceLabel}`;

  // Articles list
  const listEl = document.getElementById('newsArticlesList');

  if (!found || !articles || articles.length === 0) {
    const notFoundMsg = !backendOnline
      ? 'Backend is offline — no live news search was performed.'
      : (api_used === 'none' || !api_used)
        ? 'No news API keys configured. Add NEWS_API_KEY or GNEWS_API_KEY in backend/.env to enable live search.'
        : 'No matching coverage found in verified news channels. This may indicate the story is too niche or fabricated.';

    listEl.innerHTML = `
      <div class="news-not-found">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"
          stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <br/>${notFoundMsg}
      </div>`;
    return;
  }

  listEl.innerHTML = articles.map(a => `
    <div class="news-article-card">
      <a class="news-article-title" href="${a.url || '#'}" target="_blank" rel="noopener">
        ${a.title || 'Untitled'}
      </a>
      <div class="news-article-meta">
        <span class="news-source-badge ${a.is_trusted ? 'trusted' : 'untrusted'}">
          ${a.is_trusted
            ? `<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"
                stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`
            : ''}
          ${a.source || 'Unknown Source'}
        </span>
        ${a.published_at ? `<span class="news-article-date">${a.published_at}</span>` : ''}
      </div>
    </div>
  `).join('');
}

/* ── INIT: check backend health on load ── */
window.addEventListener('DOMContentLoaded', async () => {
  const online = await checkBackendHealth();
  if (!online) {
    document.getElementById('offlineBanner').classList.remove('hidden');
    document.getElementById('offlineBanner').style.display = 'flex';
    showToast(
      'Backend appears offline. Results will use demo data until the backend is started.',
      'warning',
      8000
    );
  }
});
