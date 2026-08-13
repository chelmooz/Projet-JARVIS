// settings.js — Persistance des réglages + mode hors-ligne.
// Dépendances : utils.js, state.js

import { state } from './state.js';
import * as utils from './utils.js';

const THEME_KEY = 'jarvis_theme';

export function getTheme() {
    return localStorage.getItem(THEME_KEY) || 'dark';
}

export function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_KEY, theme);
    const btn = document.getElementById('theme-toggle');
    if (!btn) return;
    btn.setAttribute('aria-pressed', theme === 'light');
    const icon = btn.querySelector('.icon');
    if (icon) icon.textContent = theme === 'light' ? '☀️' : '🌙';
}

export function toggleTheme() {
    setTheme(getTheme() === 'dark' ? 'light' : 'dark');
}

export function initThemeToggle() {
    const btn = document.getElementById('theme-toggle');
    if (!btn) return;
    setTheme(getTheme());
    btn.addEventListener('click', toggleTheme);
}

export function applyOfflineState(offline) {
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
    if (state.sendBtn) state.sendBtn.disabled = !!offline;
}

export async function restoreSettings() {
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

// Settings persistence listeners
document.getElementById('s-default-model')?.addEventListener('change', e => {
    localStorage.setItem('jarvis_default_model', e.target.value);
    fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: 'default_model', value: e.target.value }),
    }).catch(() => {});
});

document.getElementById('s-offline')?.addEventListener('change', e => {
    const checked = e.target.checked;
    localStorage.setItem('jarvis_offline', checked);
    fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: 'offline', value: checked }),
    }).catch(() => {});
    applyOfflineState(checked);
});

// Initialize theme toggle on load
initThemeToggle();