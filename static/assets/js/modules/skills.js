// skills.js — Onglet Skills : liste, toggle.
// Dépendances : utils.js, state.js

import { state } from './state.js';
import * as utils from './utils.js';

export async function refreshSkills() {
    const grid = document.getElementById('skills-grid');
    const statusEl = document.getElementById('skills-status');
    const count = document.getElementById('skill-count');
    utils.injectSkeletons(grid, 7);
    try {
        const resp = await fetch('/api/skills');
        if (!resp.ok) {
            grid.innerHTML = '<div class="tools-empty">API /api/skills indisponible.</div>';
            count.textContent = '?';
            return;
        }
        const data = await resp.json();
        if (!data.skills || !Array.isArray(data.skills)) {
            grid.innerHTML = '<div class="tools-empty">Reponse API invalide.</div>';
            count.textContent = '?';
            return;
        }
        const skills = data.skills;
        const enabledIds = data.enabled_ids || [];
        count.textContent = skills.length;
        statusEl.textContent = enabledIds.length + ' skill' + (enabledIds.length > 1 ? 's' : '') + ' actif' + (enabledIds.length > 1 ? 's' : '');

        if (skills.length === 0) {
            grid.innerHTML = '<div class="tools-empty">Aucun skill configure.</div>';
            return;
        }

        grid.innerHTML = skills.map(s => {
            const checked = enabledIds.includes(s.id) ? 'checked' : '';
            return `<div class="skill-card" data-id="${s.id}">
                <div class="skill-info">
                    <div class="skill-name">${s.name || s.id}</div>
                    <div class="skill-category">${s.category || ''}</div>
                    <div class="skill-desc">${s.description || ''}</div>
                </div>
                <label class="skill-toggle" title="${s.name || s.id}">
                    <input type="checkbox" ${checked} data-skill-id="${s.id}">
                    <span class="slider"></span>
                </label>
            </div>`;
        }).join('');

        // Delegation d'evenements (compatibilite CSP : pas de onchange inline)
        grid.querySelectorAll('input[data-skill-id]').forEach(input => {
            input.addEventListener('change', () => {
                toggleSkill(input.dataset.skillId, input.checked);
            });
        });
    } catch (err) {
        grid.innerHTML = '<div class="tools-empty">Erreur chargement skills: ' + utils.escHtml(err.message) + '</div>';
        count.textContent = '0';
    }
}

export async function toggleSkill(skillId, enabled) {
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