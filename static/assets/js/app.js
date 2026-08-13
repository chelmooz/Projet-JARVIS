// app.js — Bootstrap du frontend : importe les modules, initialise le DOM, câble les listeners globaux.
// Ce fichier ne contient plus de logique métier (extraite dans modules/).

import { state } from './modules/state.js';
import * as utils from './modules/utils.js';
import * as status from './modules/status.js';
import * as files from './modules/files.js';
import * as settings from './modules/settings.js';
import * as vision from './modules/vision.js';
import * as skills from './modules/skills.js';
import * as tools from './modules/tools.js';
import * as agents from './modules/agents.js';
import * as conversations from './modules/conversations.js';
import * as analytics from './modules/analytics.js';
import * as chat from './modules/chat.js';

// Exposer les fonctions legacy sur window pour compatibilité (transition)
window.escHtml = utils.escHtml;
window.debounce = utils.debounce;
window.toast = utils.toast;
window.renderMarkdown = utils.renderMarkdown;
window.buildSkeletonCard = utils.buildSkeletonCard;
window.injectSkeletons = utils.injectSkeletons;
window.loadChartJs = utils.loadChartJs;
window.autoResize = utils.autoResize;
window.cachedFetch = utils.cachedFetch;
window.apiCache = utils.apiCache;
window.CACHE_TTL = utils.CACHE_TTL;

// Chat DOM elements
const chatMessagesEl = document.getElementById('chat-messages');
const input = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');

// Stocker dans state pour accès par modules
state.chat = chatMessagesEl;
state.input = input;
state.sendBtn = sendBtn;

// --- Tab switching ---
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('tab-' + btn.dataset.tab).classList.add('active');

        if (btn.dataset.tab === 'agents') agents.refreshAgents();
        if (btn.dataset.tab === 'tools') tools.refreshTools();
        if (btn.dataset.tab === 'settings') files.refreshPathAuth();
        if (btn.dataset.tab === 'analytics') {
            await utils.loadChartJs();
            analytics.refreshAnalytics();
        }
        if (btn.dataset.tab === 'conversations') conversations.loadConvs('conv-list-main');
    });
});

// --- Debounce autoResize ---
const debouncedAutoResize = utils.debounce(() => utils.autoResize(input), 150);
input.addEventListener('input', debouncedAutoResize);

// --- Send button ---
function onSendClick() {
    if (state.isSending) return;
    state.isSending = true;
    sendBtn.disabled = true;
    input.blur();
    return chat.send();
}
sendBtn.addEventListener('click', onSendClick);

// --- Vision button in chat ---
document.getElementById('vision-btn').addEventListener('click', () => document.getElementById('image-input').click());
document.getElementById('image-input').addEventListener('change', vision.handleImageSelect);

// --- Click delegation for CSP nonce compliance ---
document.addEventListener('click', e => {
    const convItem = e.target.closest('[data-conv-id]');
    if (convItem && !e.target.closest('[data-del-conv-id]')) {
        conversations.loadConv(convItem.dataset.convId);
        return;
    }
    const delBtn = e.target.closest('[data-del-conv-id]');
    if (delBtn) {
        e.stopPropagation();
        conversations.deleteConv(delBtn.dataset.delConvId);
        return;
    }
    const revokeBtn = e.target.closest('[data-revoke-path]');
    if (revokeBtn) {
        files.revokePath(atob(revokeBtn.dataset.revokePath));
        return;
    }
});

// --- Keyboard shortcuts ---
document.addEventListener('keydown', e => {
    // Escape -> close file browser modal
    if (e.key === 'Escape') {
        files.closeBrowser();
    }
    // Ctrl+C -> focus chat
    if (e.key === 'c' && (e.ctrlKey || e.metaKey) && document.activeElement !== input) {
        e.preventDefault();
        document.querySelector('.tab-btn[data-tab="chat"]').click();
        input.focus();
    }
    // Ctrl+L -> clear chat
    if (e.key === 'l' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        chat.clearChat();
    }
});

// --- Mobile Sidebar Toggle ---
const hamburger = document.getElementById('hamburger');
const sidebar = document.getElementById('sidebar');
const sidebarBackdrop = document.getElementById('sidebar-backdrop');

if (hamburger && sidebar && sidebarBackdrop) {
    hamburger.addEventListener('click', () => {
        const isOpen = sidebar.classList.toggle('show');
        sidebarBackdrop.classList.toggle('show', isOpen);
        hamburger.setAttribute('aria-expanded', isOpen);
        hamburger.setAttribute('aria-label', isOpen ? 'Fermer le menu' : 'Ouvrir le menu');
    });

    sidebarBackdrop.addEventListener('click', () => {
        sidebar.classList.remove('show');
        sidebarBackdrop.classList.remove('show');
        hamburger.setAttribute('aria-expanded', 'false');
        hamburger.setAttribute('aria-label', 'Ouvrir le menu');
    });
}

// --- Initialize modules ---
status.startStatusPolling();
settings.restoreSettings();
skills.refreshSkills();
conversations.loadConvs();
agents.fetchModels();

// Exposer handleVisionDataUrl pour compatibilité avec boot.js / vision.js
window.handleVisionDataUrl = vision.handleVisionDataUrl;

// Exposer send pour compatibilité (chat.js)
window.send = chat.send;

// Exposer clearChat pour compatibilité
window.clearChat = chat.clearChat;

// Exposer loadConv pour compatibilité
window.loadConv = conversations.loadConv;

// Exposer deleteConv pour compatibilité
window.deleteConv = conversations.deleteConv;

// Exposer refreshPathAuth pour compatibilité
window.refreshPathAuth = files.refreshPathAuth;

// Exposer authorizePath pour compatibilité
window.authorizePath = files.authorizePath;

// Exposer revokePath pour compatibilité
window.revokePath = files.revokePath;

// Exposer switchToChat pour compatibilité
window.switchToChat = tools.switchToChat;

// Exposer refreshAnalytics pour compatibilité
window.refreshAnalytics = analytics.refreshAnalytics;

// Exposer refreshAgents pour compatibilité
window.refreshAgents = agents.refreshAgents;

// Exposer refreshTools pour compatibilité
window.refreshTools = tools.refreshTools;

// Exposer refreshSkills pour compatibilité
window.refreshSkills = skills.refreshSkills;

// Exposer loadConvs pour compatibilité
window.loadConvs = conversations.loadConvs;

// Exposer updateBadges pour compatibilité
window.updateBadges = status.updateBadges;

// Exposer maybeRevisit pour compatibilité
window.maybeRevisit = conversations.maybeRevisit;

// Exposer enhanceLastAssistant pour compatibilité
window.enhanceLastAssistant = conversations.enhanceLastAssistant;

// Exposer sendFeedback pour compatibilité
window.sendFeedback = chat.sendFeedback;

// Exposer sendImplicit pour compatibilité
window.sendImplicit = chat.sendImplicit;

// Exposer buildFeedbackRow pour compatibilité
window.buildFeedbackRow = chat.buildFeedbackRow;

// Exposer renderAssistantMsg pour compatibilité
window.renderAssistantMsg = chat.renderAssistantMsg;

// Exposer addMsg pour compatibilité
window.addMsg = chat.addMsg;

// Exposer addTyping / removeTyping pour compatibilité
window.addTyping = chat.addTyping;
window.removeTyping = chat.removeTyping;

console.log('[JARVIS] Frontend bootstrap completed');
