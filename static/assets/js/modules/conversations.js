// conversations.js — Sidebar CRUD conversations.
// Dépendances : utils.js, state.js, chat.js (pour renderAssistantMsg, maybeRevisit, enhanceLastAssistant)

import { state } from './state.js';
import * as utils from './utils.js';
import * as chat from './chat.js';

export async function loadConvs(targetId) {
    const targetIds = [...new Set([targetId, 'conv-list', 'conv-list-main'].filter(Boolean))];
    try {
        const resp = await fetch('/api/conversations');
        const data = await resp.json();
        const convs = (data.data || data).conversations || [];
        const className = convs.length === 0 ? 'sidebar-convs-list empty' : 'sidebar-convs-list';

        const html = convs.length === 0
            ? 'Aucune conversation'
            : convs.map(c => {
                const active = c.id === state.currentConvId ? ' active' : '';
                const preview = (c.title || '(sans titre)').slice(0, 50);
                const msgCount = c.msg_count || 0;
                const time = c.updated_at ? c.updated_at.slice(11, 19) : '';
                return `<div class="conv-item${active}" data-conv-id="${c.id}">
                    <div class="conv-info">
                        <div class="conv-title">${utils.escHtml(preview)}</div>
                        <div class="conv-meta">${msgCount} msg · ${time}</div>
                    </div>
                    <button class="conv-del" data-del-conv-id="${c.id}" title="Supprimer">✕</button>
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
            el.innerHTML = 'Erreur: ' + utils.escHtml(e.message);
        });
    }
}

export async function loadConv(id) {
    try {
        const resp = await fetch('/api/conversations/' + id);
        const conv = await resp.json();
        const c = conv.data || conv;
        if (c.error) return;

        state.currentConvId = c.id;
        const chatEl = document.getElementById('chat-messages');
        chatEl.innerHTML = '';

        for (const msg of (c.messages || [])) {
            if (msg.role === 'assistant') {
                chatEl.appendChild(chat.renderAssistantMsg(conv.id, msg));
                continue;
            }
            const div = document.createElement('div');
            div.className = 'msg ' + (msg.role === 'user' ? 'user' : 'system');
            div.textContent = msg.content;

            if (msg.agent) {
                const meta = document.createElement('div');
                meta.className = 'meta';
                meta.innerHTML = `<span class="badge badge-agent">${msg.agent}</span>`
                    + (msg.model ? `<span class="badge badge-model">${msg.model}</span>` : '')
                    + (msg.backend ? `<span class="badge badge-backend">${msg.backend}</span>` : '');
                div.appendChild(meta);
            }
            chatEl.appendChild(div);
        }

        if (conv.id) chat.maybeRevisit(conv);
        chatEl.scrollTop = chatEl.scrollHeight;
        loadConvs();

        const chatTab = document.querySelector('.tab-btn[data-tab="chat"]');
        if (chatTab) chatTab.click();
    } catch (e) {
        chat.addMsg('system', 'Erreur chargement: ' + e.message);
    }
}

export async function deleteConv(id) {
    try {
        await fetch('/api/conversations/' + id, { method: 'DELETE' });
        if (state.currentConvId === id) {
            state.currentConvId = null;
            document.getElementById('chat-messages').innerHTML = '<div class="msg system">Nouvelle conversation. Posez votre question.</div>';
        }
        loadConvs();
    } catch (e) {
        console.error('Delete error:', e);
    }
}

export async function clearAllConvs() {
    if (!confirm('Effacer tout l\'historique des conversations ?')) return;
    try {
        await fetch('/api/conversations', { method: 'DELETE' });
        state.currentConvId = null;
        document.getElementById('chat-messages').innerHTML = '<div class="msg system">Nouvelle conversation. Posez votre question.</div>';
        loadConvs();
    } catch (e) {
        console.error('Clear error:', e);
    }
}

export function toggleConvs() {
    state.convsExpanded = !state.convsExpanded;
    const list = document.getElementById('conv-list');
    const arrow = document.getElementById('conv-arrow');
    list.style.display = state.convsExpanded ? '' : 'none';
    arrow.classList.toggle('open', state.convsExpanded);
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
    chat.sendImplicit(conv.id, lastId, 'revisit');
}

export function enhanceLastAssistant(convId) {
    if (!convId) return;
    // Délègue à chat.js pour éviter la duplication
    // chat.enhanceLastAssistant existe déjà dans chat.js
}