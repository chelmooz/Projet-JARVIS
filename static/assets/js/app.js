const APP_VERSION = '5.4';

// --- Toast notifications ---
function toast(msg, type) {
  type = type || 'info';
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => {
    el.classList.add('removing');
    setTimeout(() => el.remove(), 300);
  }, 3000);
}

// --- Markdown renderer (basique) ---
function renderMarkdown(text) {
  const r = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => `<pre><code class="language-${lang || 'plaintext'}">${code}</code></pre>`)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^# (.+)$/gm, '<h2>$1</h2>')
    .replace(/\n/g, '<br>');
  return r;
}

// --- HTML escape pour données API non fiables ---
function escHtml(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// --- Tab switching ---
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'agents') refreshAgents();
    if (btn.dataset.tab === 'tools') refreshTools();
    if (btn.dataset.tab === 'settings') refreshPathAuth();
    if (btn.dataset.tab === 'analytics') refreshAnalytics();
    if (btn.dataset.tab === 'conversations') loadConvs('conv-list-main');
  });
});

// --- Auto-resize textarea ---
function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

// --- Chat ---
const chat = document.getElementById('chat-messages');
const input = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
let pendingImage = null;

function addMsg(role, content, meta) {
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  if (role === 'assistant') {
    div.innerHTML = renderMarkdown(content);
  } else {
    div.textContent = content;
  }
  if (meta) {
    const m = document.createElement('div');
    m.className = 'meta';
    m.innerHTML = Object.entries(meta).map(([k,v]) => `<span class="badge badge-${escHtml(k)}">${escHtml(v)}</span>`).join('');
    div.appendChild(m);
  }
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

// --- Feedback mémoire (auto-amélioration) ---
let _lastRevisit = { id: null, t: 0 };

function buildFeedbackRow(convId, msg) {
  const row = document.createElement('div');
  row.className = 'feedback-row';
  row.innerHTML =
    '<button class="fb-btn" data-act="up" title="Utile (👍)">👍</button>' +
    '<button class="fb-btn" data-act="down" title="Pas utile (👎)">👎</button>' +
    '<button class="fb-btn" data-act="copy" title="Copier la reponse">📋</button>';
  row.querySelectorAll('.fb-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const act = btn.dataset.act;
      if (act === 'copy') {
        try { await navigator.clipboard.writeText(msg.content || ''); } catch (e) {}
        sendImplicit(convId, msg.id, 'copy');
        btn.style.color = '#66ee88';
      } else {
        sendFeedback(convId, msg.id, act === 'up' ? 1 : -1);
        btn.style.opacity = '0.5';
      }
    });
  });
  return row;
}

function renderAssistantMsg(convId, msg) {
  const div = document.createElement('div');
  div.className = 'msg assistant';
  div.innerHTML = renderMarkdown(msg.content || '');
  if (msg.agent) {
    const meta = document.createElement('div');
    meta.className = 'meta';
    meta.innerHTML = `<span class="badge badge-agent">${escHtml(msg.agent)}</span>`
      + (msg.model ? `<span class="badge badge-model">${escHtml(msg.model)}</span>` : '')
      + (msg.backend ? `<span class="badge badge-backend">${escHtml(msg.backend)}</span>` : '');
    div.appendChild(meta);
  }
  if (msg.id && convId) {
    div.appendChild(buildFeedbackRow(convId, msg));
  }
  return div;
}

async function sendFeedback(convId, msgId, signal) {
  try {
    await fetch('/api/feedback', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conv_id: convId, msg_id: msgId, signal })
    });
  } catch (e) {}
}

async function sendImplicit(convId, msgId, type) {
  try {
    await fetch('/api/feedback/implicit', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conv_id: convId, msg_id: msgId, type })
    });
  } catch (e) {}
}

async function enhanceLastAssistant(convId) {
  if (!convId) return;
  try {
    const resp = await fetch('/api/conversations/' + convId);
    const conv = await resp.json();
    const c = conv.data || conv;
    if (c.error) return;
    const msgs = c.messages || [];
    let target = null;
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'assistant' && msgs[i].id) { target = msgs[i]; break; }
    }
    if (!target) return;
    const last = chat.lastElementChild;
    if (last && last.classList.contains('assistant')) {
      last.replaceWith(renderAssistantMsg(convId, target));
    }
  } catch (e) {}
}

function maybeRevisit(conv) {
  const msgs = conv.messages || [];
  let lastId = null;
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].id) { lastId = msgs[i].id; break; }
  }
  if (!lastId) return;
  const now = Date.now();
  if (_lastRevisit.id === conv.id && now - _lastRevisit.t < 60000) return;
  _lastRevisit = { id: conv.id, t: now };
  sendImplicit(conv.id, lastId, 'revisit');
}

function addTyping() {
  const div = document.createElement('div');
  div.className = 'msg assistant';
  div.id = 'typing-indicator';
  div.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function removeTyping() {
  const el = document.getElementById('typing-indicator');
  if (el) el.remove();
}

function updateBadges(agent, model, backend) {
  document.getElementById('current-agent').textContent = agent || '—';
  document.getElementById('current-model').textContent = model || '—';
  const be = document.getElementById('current-backend');
  be.textContent = backend || '—';
  be.className = 'badge badge-backend';
}

input.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
});
sendBtn.addEventListener('click', send);
document.getElementById('vision-btn').addEventListener('click', () => document.getElementById('image-input').click());
document.getElementById('image-input').addEventListener('change', handleImageSelect);
document.getElementById('upload-zone').addEventListener('click', () => document.getElementById('vision-file').click());

function handleImageSelect(e) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function(ev) { pendingImage = ev.target.result; };
  reader.readAsDataURL(file);
}

// --- Vision ---
function handleVisionFile(input) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = async function(e) {
    const preview = document.getElementById('vision-preview');
    preview.src = e.target.result;
    preview.style.display = 'block';
    document.querySelector('.upload-zone .icon').textContent = '✅';
    const result = document.getElementById('vision-result');
    result.style.display = 'block';
    result.textContent = 'Analyse en cours...';
    try {
      const resp = await fetch('/api/vision', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: e.target.result, task: 'Decris cette image en detail' })
      });
      const data = await resp.json();
      if (!resp.ok) {
        result.textContent = '❌ Erreur ' + resp.status + ' : ' + (data.error || JSON.stringify(data));
        return;
      }
      if (!data.response) {
        result.textContent = '⚠️ Reponse vide du modele vision. Verifiez que llama3.2-vision:11b est bien installe.';
        return;
      }
      result.innerHTML = '<div style="margin-bottom:6px;color:#aaa;font-size:11px;">Modele: ' + escHtml(data.model||'?') + '</div>' + renderMarkdown(data.response);
      updateBadges(data.agent, data.model, data.backend);
    } catch (err) {
      result.textContent = 'Erreur : ' + err.message;
    }
  };
  reader.readAsDataURL(file);
}

// Drag & drop
const zone = document.getElementById('upload-zone');
zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
zone.addEventListener('drop', e => {
  e.preventDefault();
  zone.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) document.getElementById('vision-file').files = e.dataTransfer.files;
  handleVisionFile(document.getElementById('vision-file'));
});

// --- Agents ---
let selectedAgent = null;
let availableModels = [];

async function fetchModels() {
  try {
    const resp = await fetch('/api/models');
    const data = await resp.json();
    availableModels = data.models || [];
  } catch (e) {
    availableModels = [];
  }
  populateDefaultModelSelect();
}

function populateDefaultModelSelect() {
  const sel = document.getElementById('s-default-model');
  if (!sel) return;
  const current = sel.value;
  const models = availableModels.length > 0 ? availableModels : ['qwen2.5'];
  sel.innerHTML = models.map(m => `<option value="${escHtml(m)}"${m === current ? ' selected' : ''}>${escHtml(m)}</option>`).join('');
}

async function refreshAgents() {
  const grid = document.getElementById('agents-grid');
  const count = document.getElementById('agent-count');
  if (availableModels.length === 0) await fetchModels();
  try {
    const resp = await fetch('/api/agents');
    if (!resp.ok) {
      grid.innerHTML = '<div class="tools-empty">API /api/agents indisponible (HTTP ' + resp.status + '). Redemarrez JARVIS (Ctrl+C puis relancez JARVIS.bat).</div>';
      return;
    }
    const data = await resp.json();
    const profiles = (data.data || {}).profiles || {};
    const keys = Object.keys(profiles);
    count.textContent = keys.length;
    if (keys.length === 0) {
      grid.innerHTML = '<div class="tools-empty">Aucun profil trouve.</div>';
      return;
    }
    let html = '';
    for (const key of keys) {
      const p = profiles[key];
      html += buildAgentCard(key, p);
    }
    grid.innerHTML = html;
    // Attach assign handlers
    document.querySelectorAll('.assign-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const profile = e.target.dataset.profile;
        const select = document.getElementById('model-' + profile);
        const model = select.value;
        if (!availableModels.includes(model)) {
          toast('Modele indisponible: ' + model, 'error');
          return;
        }
        e.target.disabled = true;
        try {
          const r = await fetch('/api/agents/assign', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ profile, model })
          });
          const res = await r.json();
          if (res.data && !res.error) toast('Modele ' + model + ' assigne a ' + profile, 'success');
          else toast('Echec assignation: ' + (res.error || '?'), 'error');
        } catch (err) {
          toast('Erreur reseau: ' + err.message, 'error');
        }
        e.target.disabled = false;
      });
    });
    // Attach chat-with-agent handlers
    document.querySelectorAll('.chat-agent-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const agent = e.target.dataset.agent;
        selectedAgent = agent;
        try {
          const [beResp, agResp] = await Promise.all([
            fetch('/api/backend'),
            fetch('/api/agents')
          ]);
          const beData = await beResp.json();
          const agData = await agResp.json();
          const profiles = (agData.data || {}).profiles || {};
          const profile = profiles[agent] || {};
          const model = profile.model || '—';
          const backend = beData.backend || '—';
          updateBadges(agent, model, backend);
        } catch (err) {
          updateBadges(agent, '—', '—');
        }
        document.querySelector('.tab-btn[data-tab="chat"]').click();
        input.focus();
        input.placeholder = `Message pour @${agent}...`;
      });
    });
  } catch (err) {
    grid.innerHTML = '<div class="tools-empty">Erreur chargement profils: ' + escHtml(err.message) + '</div>';
  }
}

function buildAgentCard(key, p) {
  const modelOpts = availableModels.length > 0
    ? availableModels.map(m =>
        `<option value="${m}" ${p.model === m ? 'selected' : ''}>${m}</option>`
      ).join('')
    : `<option value="${p.model}" selected>${p.model}</option>`;
  const skills = (p.skills || []).map(s =>
    `<span class="skill-tag">${s}</span>`
  ).join('');
  const tools = Object.entries(p.tools || {}).map(([k,v]) =>
    `<span class="tool-tag" title="${v}">${k}</span>`
  ).join('');
  const promptPreview = (p.system_prompt || '').slice(0, 200) + '...';
  return `
    <div class="agent-card">
      <div class="card-header">
        <div class="card-emoji">${p.emoji || '🤖'}</div>
        <div class="card-info">
          <div class="name">${p.name || key}</div>
          <div class="title">${p.title || ''}</div>
          <div class="priority">${p.priority || ''}</div>
        </div>
      </div>
      <div class="card-model">
        <select id="model-${key}">${modelOpts}</select>
        <button class="assign-btn" title="Assigne le modèle sélectionné à l'agent ${p.name || key}" data-profile="${key}">Appliquer</button>
        <span class="assign-status" id="status-${key}"></span>
      </div>
      <div style="margin-top:8px">
        <button class="chat-agent-btn" data-agent="${key}" style="width:100%;background:#00d4ff;color:#000;border:none;border-radius:6px;padding:8px;font-weight:700;cursor:pointer;font-size:12px;">💬 Discuter avec cet agent</button>
      </div>
      <div class="card-prompt">
        <details>
          <summary>System Prompt</summary>
          <pre>${escHtml(p.system_prompt || '')}</pre>
        </details>
      </div>
      <div class="card-skills">${skills}</div>
      <div class="card-tools">${tools}</div>
      <div class="card-signature">"${escHtml(p.signature || '')}"</div>
    </div>
  `;
}

function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

// --- Cyber Workflows ---
// --- Tools (Diagnostic) ---
async function refreshTools() {
  const grid = document.querySelector('#tab-tools .tools-grid');
  try {
    const resp = await fetch('/api/diag');
    if (!resp.ok) { grid.innerHTML = '<div class="tools-empty">API /api/diag indisponible (HTTP ' + resp.status + ')</div>'; return; }
    const data = await resp.json();
    const sections = ['host', 'cpu', 'ram', 'gpu', 'disk', 'python', 'binaries', 'network'];
    grid.innerHTML = sections.map(key => {
      const section = data[key] || {};
      let items = '';
      for (const [k, v] of Object.entries(section)) {
        items += `<div class="tools-item"><span class="tools-key">${k}</span><span class="tools-val">${escHtml(String(v))}</span></div>`;
      }
      return `<div class="tools-section"><h4>${key.toUpperCase()}</h4><div class="tools-items">${items}</div></div>`;
    }).join('');
  } catch (e) {
    grid.innerHTML = '<div class="tools-empty">Erreur: ' + escHtml(e.message) + '</div>';
  }
}

// --- Skills ---
async function refreshSkills() {
  const grid = document.getElementById('skills-grid');
  const status = document.getElementById('skills-status');
  const count = document.getElementById('skill-count');
  try {
    const resp = await fetch('/api/skills');
    if (!resp.ok) {
      grid.innerHTML = '<div class="tools-empty">API /api/skills indisponible (HTTP ' + resp.status + '). Redemarrez JARVIS (Ctrl+C puis relancez JARVIS.bat).</div>';
      count.textContent = '?';
      return;
    }
    const data = await resp.json();
    if (!data.skills || !Array.isArray(data.skills)) {
      grid.innerHTML = '<div class="tools-empty">Reponse API invalide. Redemarrez JARVIS.</div>';
      count.textContent = '?';
      return;
    }
    const skills = data.skills;
    const enabledIds = data.enabled_ids || [];
    count.textContent = skills.length;
    status.textContent = enabledIds.length + ' skill' + (enabledIds.length > 1 ? 's' : '') + ' actif' + (enabledIds.length > 1 ? 's' : '');
    if (skills.length === 0) {
      grid.innerHTML = '<div class="tools-empty">Aucun skill configure dans config/skills.json.</div>';
      return;
    }
    grid.innerHTML = skills.map(s => {
      const checked = enabledIds.includes(s.id) ? 'checked' : '';
      return `
        <div class="skill-card" data-id="${s.id}">
          <div class="skill-info">
            <div class="skill-name">${s.name || s.id}</div>
            <div class="skill-category">${s.category || ''}</div>
            <div class="skill-desc">${s.description || ''}</div>
          </div>
          <label class="skill-toggle" title="${s.name || s.id} : activer/désactiver cette règle de comportement">
            <input type="checkbox" ${checked} onchange="toggleSkill('${s.id}', this.checked)">
            <span class="slider"></span>
          </label>
        </div>
      `;
    }).join('');
  } catch (err) {
    grid.innerHTML = '<div class="tools-empty">Erreur chargement skills: ' + escHtml(err.message) + '</div>';
    count.textContent = '0';
  }
}

async function toggleSkill(skillId, enabled) {
  try {
    await fetch('/api/skills/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ skill_id: skillId })
    });
    refreshSkills();
  } catch (e) {
    console.error('Toggle failed:', e);
  }
}

// --- Status polling ---
async function pollStatus() {
  if (document.hidden) return;
  try {
    const resp = await fetch('/api/status');
    const s = await resp.json();
    const backendDot = s.ollama ? 'ok' : 'warn';
    const setSide = (id, text, cls) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.innerHTML = `<span class="status-dot dot-${cls}"></span>${text}`;
    };
    setSide('st-backend', s.backend || '?', backendDot);
    setSide('st-ollama', s.ollama ? 'OK' : 'HS', s.ollama ? 'ok' : 'err');
    setSide('st-memory', s.memory_ok ? 'OK' : 'ERR', s.memory_ok ? 'ok' : 'err');
    setSide('st-vector', s.vector_ok ? 'OK' : 'ERR', s.vector_ok ? 'ok' : 'err');
  } catch(e) {
    document.getElementById('st-backend').innerHTML = '<span class="status-dot dot-err"></span>HS';
    document.getElementById('st-ollama').innerHTML = '<span class="status-dot dot-err"></span>HS';
  }
  try {
    const mr = await fetch('/api/metrics');
    const m = await mr.json();
    const rss = m.memory && m.memory.rss_mb ? m.memory.rss_mb + ' MB' : '—';
    document.getElementById('st-rss').textContent = rss;
    document.getElementById('st-requests').textContent = (m.requests || 0).toLocaleString();
    document.getElementById('st-uptime').textContent = m.uptime_human || '—';
  } catch(e) {}
}
pollStatus();
setInterval(pollStatus, 5000);
setInterval(refreshAnalytics, 30000);

// --- Conversations ---
let currentConvId = null;
let convsExpanded = true;
document.getElementById('sidebar-convs-header').addEventListener('click', toggleConvs);
document.getElementById('clear-convs-btn').addEventListener('click', clearAllConvs);

function toggleConvs() {
  convsExpanded = !convsExpanded;
  const list = document.getElementById('conv-list');
  const arrow = document.getElementById('conv-arrow');
  list.style.display = convsExpanded ? '' : 'none';
  arrow.classList.toggle('open', convsExpanded);
}

async function loadConvs(targetId) {
  // Toujours rafraîchir la liste latérale + (si ouverte) celle de l'onglet Conversations.
  const targetIds = [...new Set([targetId, 'conv-list', 'conv-list-main'].filter(Boolean))];
  try {
    const resp = await fetch('/api/conversations');
    const data = await resp.json();
    const convs = (data.data || data).conversations || [];
    const className = convs.length === 0 ? 'sidebar-convs-list empty' : 'sidebar-convs-list';
    const html = convs.length === 0
      ? 'Aucune conversation'
      : convs.map(c => {
          const active = c.id === currentConvId ? ' active' : '';
          const preview = (c.title || '(sans titre)').slice(0, 50);
          const msgCount = c.msg_count || 0;
          const time = c.updated_at ? c.updated_at.slice(11, 19) : '';
          return `<div class="conv-item${active}" data-id="${c.id}" onclick="loadConv('${c.id}')">
            <div class="conv-info">
              <div class="conv-title">${escHtml(preview)}</div>
              <div class="conv-meta">${msgCount} msg · ${time}</div>
            </div>
            <button class="conv-del" onclick="event.stopPropagation();deleteConv('${c.id}')" title="Supprimer">✕</button>
          </div>`;
        }).join('');
    targetIds.forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      el.className = className;
      el.innerHTML = html;
    });
  } catch (e) {
    targetIds.forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      el.className = 'sidebar-convs-list empty';
      el.innerHTML = 'Erreur: ' + escHtml(e.message);
    });
  }
}

async function loadConv(id) {
  try {
    const resp = await fetch('/api/conversations/' + id);
    const conv = await resp.json();
    const c = conv.data || conv;
    if (c.error) return;
    currentConvId = c.id;
    const chat = document.getElementById('chat-messages');
    chat.innerHTML = '';
    for (const msg of (c.messages || [])) {
      if (msg.role === 'assistant') {
        chat.appendChild(renderAssistantMsg(conv.id, msg));
        continue;
      }
      const div = document.createElement('div');
      div.className = 'msg ' + (msg.role === 'user' ? 'user' : 'system');
      if (msg.role === 'user') {
        div.textContent = msg.content;
      } else {
        div.textContent = msg.content;
      }
      if (msg.agent) {
        const meta = document.createElement('div');
        meta.className = 'meta';
        meta.innerHTML = `<span class="badge badge-agent">${msg.agent}</span>`
          + (msg.model ? `<span class="badge badge-model">${msg.model}</span>` : '')
          + (msg.backend ? `<span class="badge badge-backend">${msg.backend}</span>` : '');
        div.appendChild(meta);
      }
      chat.appendChild(div);
    }
    if (conv.id) maybeRevisit(conv);
    chat.scrollTop = chat.scrollHeight;
    loadConvs();
    const chatTab = document.querySelector('.tab-btn[data-tab="chat"]');
    if (chatTab) chatTab.click();
  } catch (e) {
    addMsg('system', 'Erreur chargement: ' + e.message);
  }
}

async function deleteConv(id) {
  try {
    await fetch('/api/conversations/' + id, { method: 'DELETE' });
    if (currentConvId === id) {
      currentConvId = null;
      document.getElementById('chat-messages').innerHTML = '<div class="msg system">Nouvelle conversation. Posez votre question.</div>';
    }
    loadConvs();
  } catch (e) {
    console.error('Delete error:', e);
  }
}

async function clearAllConvs() {
  if (!confirm('Effacer tout l\'historique des conversations ?')) return;
  try {
    await fetch('/api/conversations', { method: 'DELETE' });
    currentConvId = null;
    document.getElementById('chat-messages').innerHTML = '<div class="msg system">Nouvelle conversation. Posez votre question.</div>';
    loadConvs();
  } catch (e) {
    console.error('Clear error:', e);
  }
}

async function send() {
  const text = input.value.trim();
  if (!text) return;
  const isOffline = document.getElementById('s-offline').checked;
  if (isOffline) {
    addMsg('system', '🔌 Mode hors-ligne activé. Désactivez-le dans Settings pour envoyer des messages.');
    return;
  }
  input.value = '';
  input.style.height = 'auto';
  let taskText = text;
  if (selectedAgent && !text.startsWith('@')) {
    taskText = '@' + selectedAgent + ' ' + text;
  }
  addMsg('user', taskText);
  sendBtn.disabled = true;
  addTyping();
  try {
    if (!currentConvId) {
      const titleText = text.replace(/^@\S+\s*/, '').slice(0, 60) || text.slice(0, 60);
      const cr = await fetch('/api/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: titleText })
      });
      const cd = await cr.json();
      currentConvId = (cd.data || cd).conversation_id;
    }
    const body = { task: taskText, conversation_id: currentConvId };
    if (pendingImage) { body.image = pendingImage; pendingImage = null; }
    const resp = await fetch('/api/jarvis', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await resp.json();
    removeTyping();
    const response = data.response || JSON.stringify(data, null, 2);
    addMsg('assistant', response, { agent: data.agent, model: data.model, backend: data.backend });
    updateBadges(data.agent, data.model, data.backend);
    if (data.suggested_skill) refreshSkills();
    enhanceLastAssistant(currentConvId);
    loadConvs();
  } catch (err) {
    removeTyping();
    addMsg('system', 'Erreur : ' + err.message);
  }
  sendBtn.disabled = false;
  input.focus();
}

function clearChat() {
  currentConvId = null;
  chat.innerHTML = '<div class="msg system">Nouvelle conversation. Posez votre question.</div>';
  loadConvs();
}

// --- Analytics ---
let analyticsCharts = {};
let lastVectorizeResult = null;

function destroyCharts() {
  Object.values(analyticsCharts).forEach(c => { try { c.destroy(); } catch(e) {} });
  analyticsCharts = {};
}

async function refreshAnalytics() {
  if (!document.getElementById('tab-analytics').classList.contains('active')) return;
  try {
    const [analyticsResp, metricsResp, vectorResp, agentsResp] = await Promise.all([
      fetch('/api/analytics'),
      fetch('/api/metrics'),
      fetch('/api/vectorize'),
      fetch('/api/agents'),
    ]);
    const analytics = await analyticsResp.json();
    const metrics = (await metricsResp.json()).data || {};
    const vector = await vectorResp.json();
    const agentsData = (await agentsResp.json()).data || {};
    const agentProfiles = agentsData.profiles || {};
    const agentNameMap = {};
    for (const [key, val] of Object.entries(agentProfiles)) {
      agentNameMap[key] = val.name || key;
    }

    const queries = (analytics.queries || []).filter(q => q && q.agent !== undefined);
    const totalQueries = metrics.requests || queries.length;
    const totalErrors = metrics.errors || 0;
    const vectorized = vector.total || 0;
    const pendingV = vector.pending || 0;
    const usingFallback = vector.using_fallback || false;
    const errorRate = totalQueries > 0 ? ((totalErrors / totalQueries) * 100).toFixed(1) : '0.0';
    const avgLatency = queries.length > 0
      ? (queries.reduce((s, q) => s + (q.latency_ms || 0), 0) / queries.length).toFixed(0)
      : '—';

    const vecConvs = lastVectorizeResult ? lastVectorizeResult.conversations : 0;
    const vecRemaining = lastVectorizeResult ? lastVectorizeResult.remaining : '—';
    document.getElementById('analytics-kpis').innerHTML = `
      <div class="analytics-card"><div class="value">${totalQueries}</div><div class="label">Requêtes totales</div></div>
      <div class="analytics-card"><div class="value">${errorRate}%</div><div class="label">Taux d'erreur</div></div>
      <div class="analytics-card"><div class="value">${avgLatency}</div><div class="label">Latence moyenne (ms)</div></div>
      <div class="analytics-card"><div class="value">${vectorized}</div><div class="label">Documents vectorisés</div></div>
      <div class="analytics-card"><div class="value">${pendingV}</div><div class="label">En attente d'embedding</div></div>
      <div class="analytics-card"><div class="value">${vecConvs}</div><div class="label">Conversations vectorisées</div></div>
      <div class="analytics-card"><div class="value">${vecRemaining}</div><div class="label">Restantes</div></div>
      <div class="analytics-card"><div class="value">${metrics.pipeline_runs || 0}</div><div class="label">Pipelines exécutés</div></div>
    `;

    destroyCharts();

    // Agent distribution
    const agentCounts = {};
    const agentLatencies = {};
    queries.forEach(q => {
      const agent = q.agent || 'inconnu';
      agentCounts[agent] = (agentCounts[agent] || 0) + 1;
      if (!agentLatencies[agent]) agentLatencies[agent] = [];
      agentLatencies[agent].push(q.latency_ms || 0);
    });
    const agentKeys = Object.keys(agentCounts);
    const agentLabels = agentKeys.map(k => agentNameMap[k] || k);
    const agentData = agentKeys.map(k => agentCounts[k]);
    const agentColors = ['#00d4ff','#7b2ff7','#ffaa00','#00ff88','#ff4444','#888'];

    if (Chart && agentLabels.length) {
      const ctxAgent = document.getElementById('chart-agent').getContext('2d');
      analyticsCharts.agent = new Chart(ctxAgent, {
        type: 'doughnut',
        data: { labels: agentLabels, datasets: [{ data: agentData, backgroundColor: agentColors, borderWidth: 0 }] },
        options: { responsive: true, maintainAspectRatio: true, plugins: { legend: { position: 'bottom', labels: { color: '#888', font: { size: 10 } } } } }
      });

      // Latency per agent
      const avgLatPerAgent = agentKeys.map(k => {
        const vals = agentLatencies[k];
        return vals.length ? (vals.reduce((a,b) => a+b, 0) / vals.length).toFixed(0) : 0;
      });
      const ctxLat = document.getElementById('chart-latency').getContext('2d');
      analyticsCharts.latency = new Chart(ctxLat, {
        type: 'bar',
        data: { labels: agentLabels, datasets: [{ label: 'ms', data: avgLatPerAgent, backgroundColor: '#004466', borderRadius: 4 }] },
        options: { responsive: true, maintainAspectRatio: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { color: '#666' } }, x: { ticks: { color: '#888', font: { size: 10 } } } } }
      });
    }

    // Hourly heatmap
    const hourly = new Array(24).fill(0);
    queries.forEach(q => {
      const ts = q.ts || q.timestamp;
      if (ts) {
        const h = new Date(ts * 1000).getHours();
        if (h >= 0 && h < 24) hourly[h]++;
      }
    });
    if (Chart) {
      const ctxHour = document.getElementById('chart-hourly').getContext('2d');
      analyticsCharts.hourly = new Chart(ctxHour, {
        type: 'bar',
        data: { labels: Array.from({length:24},(_,i)=>String(i).padStart(2,'0')+'h'), datasets: [{ data: hourly, backgroundColor: hourly.map(v => v > 0 ? '#004466' : '#1a1a24'), borderRadius: 2 }] },
        options: { responsive: true, maintainAspectRatio: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { color: '#666', stepSize: 1 } }, x: { ticks: { color: '#555', font: { size: 9 }, maxRotation: 0 } } } }
      });

      // Vector index pie
      const ctxVec = document.getElementById('chart-vector').getContext('2d');
      const vecTotal = vectorized + pendingV;
      analyticsCharts.vector = new Chart(ctxVec, {
        type: 'doughnut',
        data: { labels: ['Vectorisés', 'En attente'], datasets: [{ data: [vectorized, pendingV], backgroundColor: ['#00d4ff', '#2a2a3a'], borderWidth: 0 }] },
        options: { responsive: true, maintainAspectRatio: true, plugins: { legend: { position: 'bottom', labels: { color: '#888', font: { size: 10 } } } } }
      });
    }
  } catch (e) {
    document.getElementById('analytics-kpis').innerHTML = `<div class="analytics-card"><div class="label" style="color:#ff4444;">Erreur chargement analytics : ${escHtml(e.message)}</div></div>`;
  }
}

// --- Bouton vectorisation conversations ---
document.getElementById('btn-vectorize-convs')?.addEventListener('click', async () => {
  const btn = document.getElementById('btn-vectorize-convs');
  const status = document.getElementById('vectorize-status');
  btn.disabled = true;
  btn.textContent = '⏳ Vectorisation en cours...';
  status.textContent = '';
  try {
    const resp = await fetch('/api/vectorize/conversations', { method: 'POST' });
    const data = await resp.json();
    lastVectorizeResult = data;
    if (data.conversations > 0) {
      status.textContent = `✅ ${data.conversations} conversation(s) traitee(s), ${data.vectorized} document(s) vectorise(s)`;
      refreshAnalytics();
    } else {
      status.textContent = data.message || '⚠️ Aucune conversation traitee';
    }
  } catch (e) {
    status.textContent = `❌ Erreur : ${e.message}`;
  } finally {
    btn.disabled = false;
    btn.textContent = '⚡ Vectoriser les conversations (lot de 5)';
  }
});

loadConvs();
fetchModels();

// --- Keyboard shortcut ---
document.addEventListener('keydown', e => {
  if (e.key === 'c' && (e.ctrlKey || e.metaKey) && document.activeElement !== input) {
    e.preventDefault();
    document.querySelector('.tab-btn[data-tab="chat"]').click();
    input.focus();
  }
});

// --- Settings persistence ---
document.getElementById('s-default-model').addEventListener('change', e => {
  localStorage.setItem('jarvis_default_model', e.target.value);
  fetch('/api/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key: 'default_model', value: e.target.value }),
  }).catch(() => {});
});
document.getElementById('s-offline').addEventListener('change', e => {
  const checked = e.target.checked;
  localStorage.setItem('jarvis_offline', checked);
  fetch('/api/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key: 'offline', value: checked }),
  }).catch(() => {});
  applyOfflineState(checked);
});
function applyOfflineState(offline) {
  const existing = document.getElementById('offline-banner');
  if (!existing) {
    const el = document.createElement('div');
    el.id = 'offline-banner';
    el.style.cssText = 'display:none;background:#442222;color:#ff8888;text-align:center;padding:6px;font-size:13px;position:sticky;top:0;z-index:100;border-bottom:1px solid #663333;';
    el.textContent = '🔌 Mode hors-ligne activé — l\'assistant ne répondra pas';
    document.querySelector('.main')?.prepend(el);
  }
  const banner = document.getElementById('offline-banner');
  if (banner) banner.style.display = offline ? 'block' : 'none';
  const chatInput = document.getElementById('chat-input');
  if (chatInput) chatInput.placeholder = offline ? 'Mode hors-ligne — désactivez dans Settings' : 'Posez votre question à JARVIS...';
  if (sendBtn) sendBtn.disabled = !!offline;
}
// Restore: fetch from server, fallback to localStorage
async function restoreSettings() {
  try {
    const resp = await fetch('/api/settings');
    const prefs = await resp.json();
    if (prefs.offline !== undefined) {
      document.getElementById('s-offline').checked = !!prefs.offline;
      localStorage.setItem('jarvis_offline', prefs.offline);
      applyOfflineState(!!prefs.offline);
    }
  } catch (e) {
    const of = localStorage.getItem('jarvis_offline');
    if (of !== null) {
      document.getElementById('s-offline').checked = of === 'true';
      applyOfflineState(of === 'true');
    }
  }
  const dm = localStorage.getItem('jarvis_default_model');
  if (dm) document.getElementById('s-default-model').value = dm;
}
restoreSettings();
refreshSkills();

// --- File Path authorization ---
async function authorizePath() {
  const input = document.getElementById('fp-path');
  const fb = document.getElementById('fp-feedback');
  const path = input ? input.value.trim() : '';
  if (!path) return;
  try {
    const r = await fetch('/api/files/authorize', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({path}),
    });
    const data = await r.json();
    if (data.success) {
      fb.className = 'fp-feedback ok';
      fb.textContent = `✅ Dossier autorise : ${path}`;
    } else {
      fb.className = 'fp-feedback err';
      fb.textContent = `❌ Erreur : ${data.error || 'inconnue'}`;
    }
  } catch (e) {
    fb.className = 'fp-feedback err';
    fb.textContent = `❌ Erreur reseau : ${e.message}`;
  }
  input.value = '';
  refreshPathAuth();
  setTimeout(() => { fb.className = 'fp-feedback'; }, 4000);
}

async function revokePath(path) {
  const fb = document.getElementById('fp-feedback') || {};
  try {
    const r = await fetch('/api/files/authorize', {
      method: 'DELETE',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({path}),
    });
    const data = await r.json();
    if (data.success) {
      fb.className = 'fp-feedback ok';
      fb.textContent = `🔓 Acces revoque : ${path}`;
    } else {
      fb.className = 'fp-feedback err';
      fb.textContent = `❌ Erreur : ${data.error || 'inconnue'}`;
    }
  } catch (e) {
    fb.className = 'fp-feedback err';
    fb.textContent = `❌ Erreur reseau : ${e.message}`;
  }
  refreshPathAuth();
  setTimeout(() => { fb.className = 'fp-feedback'; }, 4000);
}

async function refreshPathAuth() {
  try {
    const r = await fetch('/api/files/authorized');
    const data = await r.json();
    const container = document.getElementById('fp-list');
    if (!container) return;
    if (data.paths && data.paths.length > 0) {
      container.innerHTML = data.paths.map(p =>
        `<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 8px;background:#1a1a24;border-radius:4px;">
          <span style="color:#ccc;font-family:monospace;font-size:11px;">${p}</span>
          <button onclick='revokePath(atob("${btoa(p)}"))' style="padding:2px 8px;background:#440000;color:#ff4444;border:none;border-radius:4px;cursor:pointer;font-size:10px;">Revoquer</button>
        </div>`
      ).join('');
    } else {
      container.innerHTML = '<span style="color:#555;">Aucun dossier autorise.</span>';
    }
  } catch (e) {
    console.error('refreshPathAuth error:', e);
  }
}

// --- File browser (Settings → Parcourir) ---
let fbHistory = [];

function closeBrowser() {
  document.getElementById('fb-overlay').classList.remove('show');
  fbHistory = [];
}

function openBrowser() {
  const overlay = document.getElementById('fb-overlay');
  overlay.classList.add('show');
  fbHistory = [];
  loadDrives();
}

async function loadDrives() {
  const body = document.getElementById('fb-body');
  const bread = document.getElementById('fb-breadcrumb');
  const backBtn = document.getElementById('fb-back');
  const pathInput = document.getElementById('fb-path');
  if (pathInput) pathInput.value = '';
  backBtn.style.display = 'none';
  bread.innerHTML = '<span>Lecteurs</span>';
  body.innerHTML = '<div class="fb-empty">Chargement...</div>';
  try {
    const r = await fetch('/api/files/drives');
    const data = await r.json();
    if (!data.drives || data.drives.length === 0) {
      body.innerHTML = '<div class="fb-empty">Aucun lecteur trouve.</div>';
      return;
    }
    body.innerHTML = data.drives.map(d =>
      `<div class="fb-drive" data-path="${d.name}">
        <span class="icon">💾</span>
        <span class="name">${d.name}</span>
        <span class="space">${d.free_gb} Go / ${d.total_gb} Go libres</span>
      </div>`
    ).join('');
    body.querySelectorAll('.fb-drive').forEach(el => {
      el.addEventListener('click', () => browseDir(el.dataset.path));
    });
  } catch (e) {
    body.innerHTML = '<div class="fb-empty">Erreur chargement lecteurs: ' + escHtml(e.message) + '</div>';
  }
}

async function browseDir(path) {
  const body = document.getElementById('fb-body');
  const bread = document.getElementById('fb-breadcrumb');
  const backBtn = document.getElementById('fb-back');
  const pathInput = document.getElementById('fb-path');
  if (pathInput) pathInput.value = path;
  fbHistory.push(path);
  backBtn.style.display = 'inline-block';
  body.innerHTML = '<div class="fb-empty">Chargement...</div>';
  // Build breadcrumb
  const parts = path.replace(/\\/g, '/').split('/').filter(Boolean);
  let cumul = '';
  const isDrive = /^[A-Z]:$/i.test(path.trim());
  bread.innerHTML = '<a class="fb-crumb" data-target="">Lecteurs</a>';
  parts.forEach((p, i) => {
    cumul += (i === 0 && /^[A-Z]$/i.test(p) ? ':' : '') + (i > 0 && cumul ? '/' : '') + p;
    const displayPath = cumul.match(/^[A-Z]:$/i) ? cumul + '\\' : cumul;
    if (i < parts.length - 1) {
      bread.innerHTML += ` <span>›</span> <a class="fb-crumb" data-target="${displayPath.replace(/\\/g, '/')}">${p}</a>`;
    } else {
      bread.innerHTML += ` <span>›</span> <span>${p}</span>`;
    }
  });
  bread.querySelectorAll('.fb-crumb').forEach(el => {
    el.addEventListener('click', () => {
      const t = el.dataset.target;
      if (!t) loadDrives();
      else browseDir(t.replace(/\//g, '\\'));
    });
  });
  try {
    const r = await fetch('/api/files/browse?path=' + encodeURIComponent(path));
    const data = await r.json();
    if (!data.entries || data.entries.length === 0) {
      body.innerHTML = '<div class="fb-empty">Dossier vide ou inaccessible.</div>';
      return;
    }
    body.innerHTML = data.entries.map(e =>
      `<div class="fb-folder" data-path="${e.path}">
        <span class="icon">📁</span>
        <span>${e.name}</span>
      </div>`
    ).join('');
    body.querySelectorAll('.fb-folder').forEach(el => {
      el.addEventListener('click', () => browseDir(el.dataset.path));
    });
  } catch (e) {
    body.innerHTML = '<div class="fb-empty">Erreur: ' + escHtml(e.message) + '</div>';
  }
}

function browserGoUp() {
  if (fbHistory.length <= 1) {
    loadDrives();
    return;
  }
  fbHistory.pop();
  const prev = fbHistory[fbHistory.length - 1];
  if (prev) browseDir(prev);
  else loadDrives();
}

function browserSelect() {
  const pathInput = document.getElementById('fb-path');
  if (!pathInput) return;
  const path = pathInput.value;
  if (!path) return;
  const fpPath = document.getElementById('fp-path');
  if (fpPath) fpPath.value = path;
  closeBrowser();
  authorizePath();
}

// --- File browser wiring ---
document.getElementById('fb-close')?.addEventListener('click', closeBrowser);
document.getElementById('fb-cancel-btn')?.addEventListener('click', closeBrowser);
document.getElementById('fb-select-btn')?.addEventListener('click', browserSelect);
document.getElementById('fb-back')?.addEventListener('click', browserGoUp);
document.getElementById('fp-browse')?.addEventListener('click', openBrowser);
document.getElementById('fp-path')?.addEventListener('keydown', e => { if (e.key === 'Enter') authorizePath(); });
