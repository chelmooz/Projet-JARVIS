// agents.js — Onglet Agents : liste, assignation modèles.
// Dépendances : utils.js, state.js

import { state } from './state.js';
import * as utils from './utils.js';
import * as status from './status.js';

export async function fetchModels() {
    try {
        const resp = await fetch('/api/models');
        const data = await resp.json();
        state.availableModels = data.models || [];
    } catch (e) {
        state.availableModels = [];
    }
    populateDefaultModelSelect();
}

export function populateDefaultModelSelect() {
    const sel = document.getElementById('s-default-model');
    if (!sel) return;
    const current = sel.value;
    const models = state.availableModels.length > 0 ? state.availableModels : ['hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M'];
    sel.innerHTML = models.map(m => `<option value="${utils.escHtml(m)}"${m === current ? ' selected' : ''}>${utils.escHtml(m)}</option>`).join('');
}

export async function refreshAgents() {
    const grid = document.getElementById('agents-grid');
    const count = document.getElementById('agent-count');
    utils.injectSkeletons(grid, 4);
    if (state.availableModels.length === 0) await fetchModels();

    try {
        const data = await utils.cachedFetch('/api/agents');
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

        document.querySelectorAll('.assign-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const profile = e.target.dataset.profile;
                const select = document.getElementById('model-' + profile);
                const model = select.value;

                if (!state.availableModels.includes(model)) {
                    utils.toast('Modele indisponible: ' + model, 'error');
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
                    if (res.data && !res.error) utils.toast('Modele ' + model + ' assigne a ' + profile, 'success');
                    else utils.toast('Echec assignation: ' + (res.error || '?'), 'error');
                } catch (err) {
                    utils.toast('Erreur reseau: ' + err.message, 'error');
                }
                e.target.disabled = false;
            });
        });

        document.querySelectorAll('.chat-agent-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const agent = e.target.dataset.agent;
                state.selectedAgent = agent;
                try {
                    const [beResp, agData] = await Promise.all([
                        fetch('/api/backend'),
                        utils.cachedFetch('/api/agents')
                    ]);
                    const beData = await beResp.json();
                    const profs = (agData.data || {}).profiles || {};
                    const profile = profs[agent] || {};
                    const model = profile.model || '—';
                    const backend = beData.backend || '—';
                    status.updateBadges(agent, model, backend);
                } catch (err) {
                    status.updateBadges(agent, '—', '—');
                }
                document.querySelector('.tab-btn[data-tab="chat"]').click();
                state.input.focus();
                state.input.placeholder = `Message pour @${agent}...`;
            });
        });
    } catch (err) {
        grid.innerHTML = '<div class="tools-empty">Erreur chargement profils: ' + utils.escHtml(err.message) + '</div>';
    }
}

export function buildAgentCard(key, p) {
    const modelOpts = state.availableModels.length > 0
        ? state.availableModels.map(m => `<option value="${m}" ${p.model === m ? 'selected' : ''}>${m}</option>`).join('')
        : `<option value="${p.model}" selected>${p.model}</option>`;

    const skills = (p.skills || []).map(s => `<span class="skill-tag">${s}</span>`).join('');
    const tools = Object.entries(p.tools || {}).map(([k, v]) => `<span class="tool-tag" title="${v}">${k}</span>`).join('');

    return `<div class="agent-card">
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
            <button class="assign-btn" title="Assigne le modèle" data-profile="${key}">Appliquer</button>
            <span class="assign-status" id="status-${key}"></span>
        </div>
        <div class="mt-8">
            <button class="chat-agent-btn agent-btn-primary" data-agent="${key}">💬 Discuter avec cet agent</button>
        </div>
        <div class="card-prompt">
            <details>
                <summary>System Prompt</summary>
                <pre>${utils.escHtml(p.system_prompt || '')}</pre>
            </details>
        </div>
        <div class="card-skills">${skills}</div>
        <div class="card-tools">${tools}</div>
        <div class="card-signature">"${utils.escHtml(p.signature || '')}"</div>
    </div>`;
}