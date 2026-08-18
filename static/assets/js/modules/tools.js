// tools.js — Onglet Outils / Diagnostic.
// Dépendances : utils.js, state.js

import { state } from './state.js';
import * as utils from './utils.js';

// --- Rendu des valeurs de /api/diag ---
// Les sections peuvent contenir des primitives, des tableaux plats
// (ex: missing_deps: []) ou des objets/tableaux imbriqués (ex: network.ports,
// binaries: [{name, path, exists}]). Ces deux derniers cas ne doivent JAMAIS
// finir en JSON.stringify brut dans une cellule : ça déborde et chevauche le
// libellé (voir historique — capture d'écran "outils dégueule de partout").

function renderPrimitive(v) {
    if (v === null || v === undefined) return '—';
    if (Array.isArray(v)) return v.length ? v.join(', ') : '—';
    return String(v);
}

function renderKeyValue(k, v) {
    if (v !== null && typeof v === 'object' && !Array.isArray(v)) {
        const sub = Object.entries(v).map(([sk, sv]) => renderKeyValue(sk, sv)).join('');
        return `<div class="tools-item tools-item--nested"><span class="tools-key">${utils.escHtml(k)}</span></div>` +
            `<div class="tools-nested">${sub}</div>`;
    }
    const val = renderPrimitive(v);
    return `<div class="tools-item"><span class="tools-key">${utils.escHtml(k)}</span><span class="tools-val">${utils.escHtml(val)}</span></div>`;
}

// Pour les sections qui sont des tableaux d'objets (ex: binaries).
function renderEntryAsItem(entry) {
    if (entry !== null && typeof entry === 'object' && !Array.isArray(entry)) {
        const title = entry.name ? String(entry.name) : '—';
        const sub = Object.entries(entry)
            .filter(([k]) => k !== 'name')
            .map(([k, v]) => renderKeyValue(k, v)).join('');
        return `<div class="tools-item tools-item--nested"><span class="tools-key">${utils.escHtml(title)}</span></div>` +
            `<div class="tools-nested">${sub}</div>`;
    }
    return `<div class="tools-item"><span class="tools-val">${utils.escHtml(renderPrimitive(entry))}</span></div>`;
}

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
            const items = Array.isArray(section)
                ? section.map(renderEntryAsItem).join('')
                : Object.entries(section).map(([k, v]) => renderKeyValue(k, v)).join('');
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