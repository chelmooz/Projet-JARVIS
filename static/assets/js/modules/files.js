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
    bread.innerHTML = '<span>Lecteurs & Partitions</span>';
    body.innerHTML = '<div class="fb-empty">Chargement...</div>';

    try {
        let r = await fetch('/api/files/all_drives');
        let data;
        let useExtended = true;
        if (r.ok) {
            data = await r.json();
        } else {
            r = await fetch('/api/files/drives');
            data = await r.json();
            useExtended = false;
        }

        let html = '';

        if (useExtended && data.success) {
            if (data.mounted_drives && data.mounted_drives.length > 0) {
                html += '<div class="fb-section-title">💾 Disques montés</div>';
                html += data.mounted_drives.map(d =>
                    `<div class="fb-drive" data-path="${d.name}">
                        <span class="icon">💾</span>
                        <span class="name">${d.name}</span>
                        <span class="fstype">${d.fstype || ''}</span>
                        <span class="space">${d.free_gb} Go / ${d.total_gb} Go libres</span>
                    </div>`
                ).join('');
            }

            if (data.physical_disks && data.physical_disks.length > 0) {
                for (const disk of data.physical_disks) {
                    const unmountedParts = disk.partitions.filter(p => !p.mounted);
                    if (unmountedParts.length === 0) continue;
                    html += `<div class="fb-section-title">🖴 ${utils.escHtml(String(disk.name))} (${disk.size_gb} Go)</div>`;
                    for (const part of unmountedParts) {
                        const fs = part.filesystem || 'Unknown';
                        const isLinux = part.is_linux_fs;
                        const isMac = part.is_macos_fs;
                        const isEnc = part.is_encrypted;
                        let icon = '❓';
                        let fsClass = '';
                        let actionsHtml = '';

                        if (isLinux) {
                            icon = '🐧';
                            fsClass = 'linux-fs';
                            const canMount = data.has_ext2fsd && data.ext2fsd_running;
                            actionsHtml += canMount
                                ? `<button class="fb-mount-btn" data-disk="${disk.number}" data-part="${part.number}">Monter</button>`
                                : `<span class="fb-mount-hint" title="${data.ext2fsd_running ? 'Ext2Fsd absent' : 'Service Ext2Fsd non démarré'}">${data.ext2fsd_running ? 'Ext2Fsd requis' : 'Démarrer Ext2Fsd'}</span>`;
                            actionsHtml += `<button class="fb-read-btn" data-disk="${disk.number}" data-part="${part.number}" title="Lecture directe (admin requis)">Lire</button>`;
                        } else if (isMac) {
                            icon = '🍎';
                            fsClass = 'macos-fs';
                            actionsHtml += '<span class="fb-mount-hint">APFS/HFS+ non supporté</span>';
                        } else if (isEnc) {
                            icon = '🔒';
                            fsClass = 'encrypted-fs';
                            actionsHtml += '<span class="fb-mount-hint">Partition chiffrée</span>';
                        }

                        html += `<div class="fb-partition ${fsClass}">
                            <span class="icon">${icon}</span>
                            <span class="name">Partition ${part.number}</span>
                            <span class="fstype">${utils.escHtml(fs)}</span>
                            <span class="size">${part.size_gb} Go</span>
                            <span class="actions">${actionsHtml}</span>
                        </div>`;
                    }
                }
            }
        } else if (data.drives && data.drives.length > 0) {
            html += data.drives.map(d =>
                `<div class="fb-drive" data-path="${d.name}">
                    <span class="icon">💾</span>
                    <span class="name">${d.name}</span>
                    <span class="space">${d.free_gb} Go / ${d.total_gb} Go libres</span>
                </div>`
            ).join('');
        } else {
            html = '<div class="fb-empty">Aucun lecteur trouvé.</div>';
        }

        body.innerHTML = html;

        body.querySelectorAll('.fb-drive').forEach(el => {
            el.addEventListener('click', () => browseDir(el.dataset.path));
        });

        body.querySelectorAll('.fb-mount-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                await mountExt4Partition(
                    parseInt(btn.dataset.disk, 10),
                    parseInt(btn.dataset.part, 10),
                    btn,
                );
            });
        });

        body.querySelectorAll('.fb-read-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                await readExt4Direct(
                    parseInt(btn.dataset.disk, 10),
                    parseInt(btn.dataset.part, 10),
                    btn,
                );
            });
        });

    } catch (e) {
        body.innerHTML = '<div class="fb-empty">Erreur chargement: ' + utils.escHtml(e.message) + '</div>';
    }
}

async function mountExt4Partition(diskNumber, partitionNumber, btn) {
    btn.disabled = true;
    btn.textContent = 'Montage...';
    try {
        const r = await fetch('/api/files/mount_ext4', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ disk_number: diskNumber, partition_number: partitionNumber }),
        });
        const data = await r.json();
        if (data.success) {
            btn.textContent = `✅ ${data.mount_point}`;
            btn.classList.add('mounted');
            btn.disabled = false;
            btn.onclick = () => browseDir(data.mount_point);
        } else {
            btn.textContent = '❌ Erreur';
            btn.title = data.error || 'Erreur inconnue';
            setTimeout(() => { btn.textContent = 'Monter'; btn.disabled = false; }, 4000);
        }
    } catch {
        btn.textContent = '❌ Réseau';
        setTimeout(() => { btn.textContent = 'Monter'; btn.disabled = false; }, 3000);
    }
}

async function readExt4Direct(diskNumber, partitionNumber, btn) {
    btn.disabled = true;
    btn.textContent = 'Lecture...';
    try {
        const r = await fetch('/api/files/read_ext4_direct', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                disk_number: diskNumber,
                partition_number: partitionNumber,
                target_path: '/',
            }),
        });
        const data = await r.json();
        if (data.success && data.entries) {
            showExt4Content(data.entries, `Disk ${diskNumber} Part ${partitionNumber}`);
        } else {
            btn.textContent = '❌ Erreur';
            btn.title = data.error || 'Erreur inconnue';
            setTimeout(() => { btn.textContent = 'Lire'; btn.disabled = false; }, 4000);
        }
    } catch {
        btn.textContent = '❌ Réseau';
        setTimeout(() => { btn.textContent = 'Lire'; btn.disabled = false; }, 3000);
    }
}

function showExt4Content(entries, label) {
    const overlay = document.createElement('div');
    overlay.className = 'fb-ext4-overlay show';
    overlay.innerHTML = `
        <div class="fb-ext4-modal">
            <div class="fb-ext4-header">
                <h3>🐧 Contenu ext4 (${utils.escHtml(label)})</h3>
                <button class="fb-ext4-close" aria-label="Fermer">×</button>
            </div>
            <div class="fb-ext4-body">
                ${entries.map(e => `
                    <div class="fb-ext4-entry ${e.is_dir ? 'is-dir' : 'is-file'}">
                        <span class="icon">${e.is_dir ? '📁' : '📄'}</span>
                        <span class="name">${utils.escHtml(e.name)}</span>
                        ${!e.is_dir ? `<span class="size">${Math.round(e.size / 1024)} Ko</span>` : ''}
                    </div>
                `).join('')}
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelector('.fb-ext4-close').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
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