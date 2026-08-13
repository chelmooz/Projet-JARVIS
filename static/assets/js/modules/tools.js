// tools.js — Onglet Outils / Diagnostic.
// Dépendances : utils.js, state.js

import { state } from './state.js';
import * as utils from './utils.js';

export async function refreshTools() {
    const grid = document.querySelector('#tab-tools .tools-grid');
    utils.injectSkeletons(grid, 6);
    try {
        const resp = await fetch('/api/diag');
        if (!resp.ok) { grid.innerHTML = '<div class="tools-empty">API /api/diag indisponible (HTTP ' + resp.status + ')</div>'; return; }
        const data = await resp.json();
        const sections = ['host', 'cpu', 'ram', 'gpu', 'disk', 'python', 'binaries', 'network'];
        grid.innerHTML = sections.map(key => {
            const section = data[key] || {};
            let items = '';
            for (const [k, v] of Object.entries(section)) {
                const val = (v !== null && typeof v === 'object') ? JSON.stringify(v) : String(v);
                items += `<div class="tools-item"><span class="tools-key">${k}</span><span class="tools-val">${utils.escHtml(val)}</span></div>`;
            }
            return `<div class="tools-section"><h4>${key.toUpperCase()}</h4><div class="tools-items">${items}</div></div>`;
        }).join('');
        const actions = document.createElement('div');
        actions.className = 'tools-actions';
        actions.innerHTML =
            '<button class="tool-action-btn" id="btn-tool-witr">🔍 Analyser un processus (witr)</button>' +
            '<button class="tool-action-btn" id="btn-tool-psinfo">📊 État système détaillé (psinfo)</button>' +
            '<span class="tools-actions-hint">Ouvre le chat avec la commande pré-remplie</span>';
        grid.appendChild(actions);
        document.getElementById('btn-tool-witr').addEventListener('click', () => {
            const target = prompt('Nom du processus ou port (ex: explorer, 8080) :');
            if (target) switchToChat(`pourquoi le processus ${target} tourne`);
        });
        document.getElementById('btn-tool-psinfo').addEventListener('click', () => {
            switchToChat('état détaillé du système');
        });
    } catch (e) {
        grid.innerHTML = '<div class="tools-empty">Erreur: ' + utils.escHtml(e.message) + '</div>';
    }
}

export function switchToChat(text) {
    document.querySelector('.tab-btn[data-tab="chat"]')?.click();
    const input = document.getElementById('chat-input');
    if (input) {
        input.value = text;
        input.focus();
        utils.autoResize(input);
    }
}