// files.js — File browser + autorisation chemins.
// Dépendances : utils.js, state.js

import { state } from './state.js';
import * as utils from './utils.js';

const FOCUSABLE_SELECTOR = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

function getFocusableElements(container) {
    return container.querySelectorAll(FOCUSABLE_SELECTOR);
}

function trapTabKey(e, firstFocusable, lastFocusable) {
    if (e.key === 'Tab') {
        if (e.shiftKey) {
            if (document.activeElement === firstFocusable) {
                e.preventDefault();
                lastFocusable.focus();
            }
        } else {
            if (document.activeElement === lastFocusable) {
                e.preventDefault();
                firstFocusable.focus();
            }
        }
    }
}

export function closeBrowser() {
    const overlay = document.getElementById('fb-overlay');
    const modal = document.querySelector('.fb-modal');
    if (modal && modal._trapHandler) {
        modal.removeEventListener('keydown', modal._trapHandler);
        delete modal._trapHandler;
    }
    if (overlay._lastFocused && overlay._lastFocused.focus) {
        overlay._lastFocused.focus();
    }
    overlay.classList.remove('show');
    state.fbHistory = [];
}

export function openBrowser() {
    const overlay = document.getElementById('fb-overlay');
    overlay._lastFocused = document.activeElement;
    overlay.classList.add('show');
    state.fbHistory = [];
    loadDrives();

    const modal = document.querySelector('.fb-modal');
    const focusableEls = getFocusableElements(modal);
    const firstFocusable = focusableEls[0];
    const lastFocusable = focusableEls[focusableEls.length - 1];

    function handler(e) {
        trapTabKey(e, firstFocusable, lastFocusable);
    }
    modal._trapHandler = handler;
    modal.addEventListener('keydown', handler);

    if (firstFocusable) firstFocusable.focus();
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
        body.innerHTML = '<div class="fb-empty">Erreur chargement lecteurs: ' + utils.escHtml(e.message) + '</div>';
    }
}

export async function browseDir(path) {
    const body = document.getElementById('fb-body');
    const bread = document.getElementById('fb-breadcrumb');
    const backBtn = document.getElementById('fb-back');
    const pathInput = document.getElementById('fb-path');

    if (pathInput) pathInput.value = path;
    state.fbHistory.push(path);
    backBtn.style.display = 'inline-block';
    body.innerHTML = '<div class="fb-empty">Chargement...</div>';

    const parts = path.replace(/\\/g, '/').split('/').filter(Boolean);
    let cumul = '';
    bread.innerHTML = '<a class="fb-crumb" data-target="">Lecteurs</a>';

    parts.forEach((p, i) => {
        cumul += (i === 0 && /^[A-Z]$/i.test(p) ? ':' : '') + (i > 0 && cumul ? '/' : '') + p;
        const displayPath = cumul.match(/^[A-Z]:$/i) ? cumul + '\\' : cumul;

        if (i < parts.length - 1) {
            bread.innerHTML += `<span>›</span> <a class="fb-crumb" data-target="${displayPath.replace(/\\/g, '/')}">${p}</a>`;
        } else {
            bread.innerHTML += `<span>›</span> <span>${p}</span>`;
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
        body.innerHTML = '<div class="fb-empty">Erreur: ' + utils.escHtml(e.message) + '</div>';
    }
}

export function browserGoUp() {
    if (state.fbHistory.length <= 1) {
        loadDrives();
        return;
    }
    state.fbHistory.pop();
    const prev = state.fbHistory[state.fbHistory.length - 1];
    if (prev) browseDir(prev);
    else loadDrives();
}

export function browserSelect() {
    const pathInput = document.getElementById('fb-path');
    if (!pathInput) return;
    const path = pathInput.value;
    if (!path) return;

    const fpPath = document.getElementById('fp-path');
    if (fpPath) fpPath.value = path;
    closeBrowser();
    authorizePath();
}

export async function authorizePath(explicitPath) {
    const pathInput = document.getElementById('fp-path');
    const fb = document.getElementById('fp-feedback');
    const path = explicitPath || (pathInput ? pathInput.value.trim() : '');
    if (!path) return;

    try {
        const r = await fetch('/api/files/authorize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
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
    pathInput.value = '';
    refreshPathAuth();
    setTimeout(() => { fb.className = 'fp-feedback'; }, 4000);
}

export async function revokePath(path) {
    const fb = document.getElementById('fp-feedback') || {};
    try {
        const r = await fetch('/api/files/authorize', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
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

export async function refreshPathAuth() {
    try {
        const r = await fetch('/api/files/authorized');
        const data = await r.json();
        const container = document.getElementById('fp-list');
        if (!container) return;

        if (data.paths && data.paths.length > 0) {
            container.innerHTML = data.paths.map(p =>
                `<div class="path-row">
                    <span class="path-name">${p}</span>
                    <button class="revoke-btn" data-revoke-path="${btoa(p)}">Revoquer</button>
                </div>`
            ).join('');
        } else {
            container.innerHTML = '<span class="empty-paths">Aucun dossier autorise.</span>';
        }
    } catch (e) {
        console.error('refreshPathAuth error:', e);
    }
}

// --- File browser wiring ---
document.getElementById('fb-close')?.addEventListener('click', closeBrowser);
document.getElementById('fb-cancel-btn')?.addEventListener('click', closeBrowser);
document.getElementById('fb-select-btn')?.addEventListener('click', browserSelect);
document.getElementById('fb-back')?.addEventListener('click', browserGoUp);
document.getElementById('fp-browse')?.addEventListener('click', openBrowser);
const debouncedAuthorize = utils.debounce(() => {
    const v = document.getElementById('fp-path')?.value.trim();
    if (v) authorizePath(v);
}, 300);

document.getElementById('fp-path')?.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); debouncedAuthorize(); } });