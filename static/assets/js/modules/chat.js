// chat.js — Logique du chat : envoi, rendu, SSE, feedback.
// Dépendances : utils.js, state.js, status.js, conversations.js

import { state } from './state.js';
import * as utils from './utils.js';
import * as status from './status.js';
import * as skills from './skills.js';
import * as conversations from './conversations.js';

const BADGE_ID = 'chat-image-badge';
const CLEAR_ID = 'chat-image-clear';
const CHAT_INPUT_ID = 'chat-input';

function readClipboardImage(e) {
    const items = e.clipboardData?.items;
    if (!items) return null;
    for (const item of items) {
        if (item.type?.startsWith('image/')) return item.getAsFile();
    }
    return null;
}

// --- ChatImage — image jointe au message (Ctrl+V + badge) ---
export class ChatImage {
    constructor() {
        this._dataUrl = null;
        this._badgeEl = null;
        this._clearEl = null;
    }

    init() {
        this._badgeEl = document.getElementById(BADGE_ID);
        this._clearEl = document.getElementById(CLEAR_ID);
        if (this._clearEl) {
            this._clearEl.addEventListener('click', () => this.clear());
        }
        document.addEventListener('paste', (e) => this._handlePaste(e), true);
    }

    pendingImage() {
        return this._dataUrl;
    }

    setImage(dataUrl) {
        this._dataUrl = dataUrl || null;
        this._render();
    }

    clear() {
        this._dataUrl = null;
        this._render();
    }

    _handlePaste(e) {
        const file = readClipboardImage(e);
        if (!file || e.target?.id === CHAT_INPUT_ID) return;
        e.preventDefault();
        const reader = new FileReader();
        reader.onload = () => this.setImage(reader.result);
        reader.readAsDataURL(file);
    }

    _render() {
        if (this._badgeEl) {
            this._badgeEl.classList.toggle('d-none', !this._dataUrl);
            if (this._dataUrl) {
                this._badgeEl.title = 'Image jointe — Ctrl+V pour la remplacer, ✕ pour la retirer';
            }
        }
    }
}

// --- Chat core functions ---

export function addMsg(role, content, meta) {
    const chatEl = document.getElementById('chat-messages');
    if (!chatEl) return;
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    if (role === 'assistant') {
        div.innerHTML = utils.renderMarkdown(content);
    } else {
        div.textContent = content;
    }
    if (meta) {
        const m = document.createElement('div');
        m.className = 'meta';
        m.innerHTML = Object.entries(meta).map(([k, v]) => `<span class="badge badge-${utils.escHtml(k)}">${utils.escHtml(v)}</span>`).join('');
        div.appendChild(m);
    }
    chatEl.appendChild(div);
    chatEl.scrollTop = chatEl.scrollHeight;
}

export function renderAssistantMsg(convId, msg) {
    const div = document.createElement('div');
    div.className = 'msg assistant';
    div.innerHTML = utils.renderMarkdown(msg.content || '');

    if (msg.agent) {
        const meta = document.createElement('div');
        meta.className = 'meta';
        meta.innerHTML = `<span class="badge badge-agent">${utils.escHtml(msg.agent)}</span>`
            + (msg.model ? `<span class="badge badge-model">${utils.escHtml(msg.model)}</span>` : '')
            + (msg.backend ? `<span class="badge badge-backend">${utils.escHtml(msg.backend)}</span>` : '');
        div.appendChild(meta);
    }

    if (msg.id && convId) {
        div.appendChild(buildFeedbackRow(convId, msg));
    }
    return div;
}

export function buildFeedbackRow(convId, msg) {
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

export async function sendFeedback(convId, msgId, signal) {
    try {
        await fetch('/api/feedback', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ conv_id: convId, msg_id: msgId, signal })
        });
        if (signal === 1) utils.toast('Merci pour votre retour 👍', 'success');
        else utils.toast('Noté, on fera mieux 👎', 'info');
    } catch (e) {}
}

export async function sendImplicit(convId, msgId, type) {
    try {
        await fetch('/api/feedback/implicit', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ conv_id: convId, msg_id: msgId, type })
        });
        if (type === 'copy') utils.toast('Réponse copiée 📋', 'success');
    } catch (e) {}
}

export async function enhanceLastAssistant(convId) {
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

        const last = state.chat?.lastElementChild;
        if (last && last.classList.contains('assistant')) {
            last.replaceWith(renderAssistantMsg(convId, target));
        }
    } catch (e) {}
}

export function maybeRevisit(conv) {
    const msgs = conv.messages || [];
    let lastId = null;
    for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].id) { lastId = msgs[i].id; break; }
    }
    if (!lastId) return;

    const now = Date.now();
    if (state._lastRevisit.id === conv.id && now - state._lastRevisit.t < 60000) return;
    state._lastRevisit = { id: conv.id, t: now };
    sendImplicit(conv.id, lastId, 'revisit');
}

export function addTyping() {
    const chatEl = document.getElementById('chat-messages');
    if (!chatEl) return;
    const div = document.createElement('div');
    div.className = 'msg assistant';
    div.id = 'typing-indicator';
    div.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
    chatEl.appendChild(div);
    chatEl.scrollTop = chatEl.scrollHeight;
}

export function removeTyping() {
    const el = document.getElementById('typing-indicator');
    if (el) el.remove();
}

export function parseSseEvent(frame) {
    let ev = null;
    let data = '';
    for (const line of frame.split('\n')) {
        if (line.startsWith('event:')) ev = line.slice(6).trim();
        else if (line.startsWith('data:')) data += line.slice(5).trim();
    }
    if (ev === null) return null;
    let payload = {};
    try { payload = data ? JSON.parse(data) : {}; } catch (e) {}
    return { event: ev, data: payload };
}

export function clearChat() {
    state.currentConvId = null;
    const chatEl = document.getElementById('chat-messages');
    if (chatEl) chatEl.innerHTML = '<div class="msg system">Nouvelle conversation. Posez votre question.</div>';
    conversations.loadConvs();
}

export async function send() {
    const text = state.input?.value.trim();
    if (!text) return;

    const isOffline = document.getElementById('s-offline')?.checked;
    if (isOffline) {
        addMsg('system', '🔌 Mode hors-ligne activé. Désactivez-le dans Settings pour envoyer des messages.');
        return;
    }

    state.input.value = '';
    state.input.style.height = 'auto';

    let taskText = text;
    if (state.selectedAgent && !text.startsWith('@')) {
        taskText = '@' + state.selectedAgent + ' ' + text;
    }

    addMsg('user', taskText);
    addTyping();

    try {
        if (!state.currentConvId) {
            const titleText = text.replace(/^@\S+\s*/, '').slice(0, 60) || text.slice(0, 60);
            const cr = await fetch('/api/conversations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: titleText })
            });
            const cd = await cr.json();
            state.currentConvId = (cd.data || cd).conversation_id;
        }

        const body = { task: taskText, conversation_id: state.currentConvId };
        const pastedImage = (window.__jarvisImage && window.__jarvisImage.pendingImage()) || null;
        if (pastedImage) { body.image = pastedImage; window.__jarvisImage.clear(); }
        else if (state.pendingImage) { body.image = state.pendingImage; state.pendingImage = null; }

        const resp = await fetch('/api/jarvis', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
            body: JSON.stringify(body)
        });

        removeTyping();

        const ctype = resp.headers.get('content-type') || '';
        if (ctype.startsWith('text/event-stream')) {
            const chatEl = document.getElementById('chat-messages');
            if (!chatEl) return;
            const div = document.createElement('div');
            div.className = 'msg assistant';
            chatEl.appendChild(div);
            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let buf = '';
            let acc = '';
            let meta = null;
            let lastRender = 0;

            const render = () => {
                const now = Date.now();
                if (now - lastRender > 120) {
                    lastRender = now;
                    div.innerHTML = utils.renderMarkdown(acc);
                    chatEl.scrollTop = chatEl.scrollHeight;
                }
            };

            for (;;) {
                const { done, value } = await reader.read();
                if (done) break;
                buf += decoder.decode(value, { stream: true });
                for (let idx = buf.indexOf('\n\n'); idx >= 0; idx = buf.indexOf('\n\n')) {
                    const evt = parseSseEvent(buf.slice(0, idx));
                    buf = buf.slice(idx + 2);
                    if (!evt) continue;
                    if (evt.event === 'token') {
                        acc += evt.data.token || '';
                        render();
                    } else if (evt.event === 'done') {
                        meta = evt.data;
                        acc = meta.response || acc;
                        lastRender = 0;
                        render();
                    }
                }
            }
            if (meta) {
                div.innerHTML = utils.renderMarkdown(meta.response || acc);
                const pair = [];
                if (meta.agent) pair.push(['agent', meta.agent]);
                if (meta.model) pair.push(['model', meta.model]);
                if (meta.backend) pair.push(['backend', meta.backend]);
                if (pair.length) {
                    const m = document.createElement('div');
                    m.className = 'meta';
                    m.innerHTML = pair.map(([k, v]) => '<span class="badge badge-' + utils.escHtml(k) + '">' + utils.escHtml(v) + '</span>').join('');
                    div.appendChild(m);
                }
                status.updateBadges(meta.agent, meta.model, meta.backend);
                if (meta.suggested_skill) skills.refreshSkills();
            }
            chatEl.scrollTop = chatEl.scrollHeight;
            enhanceLastAssistant(state.currentConvId);
            conversations.loadConvs();
        } else {
            const data = await resp.json();

            const response = data.response || JSON.stringify(data, null, 2);
            addMsg('assistant', response, { agent: data.agent, model: data.model, backend: data.backend });
            status.updateBadges(data.agent, data.model, data.backend);

            if (data.suggested_skill) skills.refreshSkills();
            enhanceLastAssistant(state.currentConvId);
            conversations.loadConvs();
        }
    } catch (err) {
        removeTyping();
        addMsg('system', 'Erreur : ' + err.message);
    }
    state.isSending = false;
    if (state.sendBtn) state.sendBtn.disabled = false;
    state.input?.focus();
}