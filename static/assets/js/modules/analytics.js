// analytics.js — Onglet Analytics : KPIs + Chart.js.
// Dépendances : utils.js, state.js, status.js

import { state } from './state.js';
import * as utils from './utils.js';
import * as status from './status.js';

export function updateOrCreateChart(canvasId, type, labels, datasets, options) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    if (state.analyticsCharts[canvasId]) {
        const chart = state.analyticsCharts[canvasId];
        chart.data.labels = labels;
        chart.data.datasets = datasets;
        chart.update();
        return chart;
    }

    state.analyticsCharts[canvasId] = new Chart(canvas.getContext('2d'), {
        type: type,
        data: { labels: labels, datasets: datasets },
        options: options
    });
    return state.analyticsCharts[canvasId];
}

export async function refreshAnalytics() {
    if (!document.getElementById('tab-analytics').classList.contains('active')) return;
    utils.injectSkeletons(document.getElementById('analytics-kpis'), 8);

    try {
        const [analyticsResp, metricsResp, vectorResp, agentsData] = await Promise.all([
            fetch('/api/analytics'),
            fetch('/api/metrics'),
            fetch('/api/vectorize'),
            utils.cachedFetch('/api/agents')
        ]);

        const analytics = await analyticsResp.json();
        const metrics = (await metricsResp.json()).data || {};
        const vector = await vectorResp.json();
        const agentProfiles = (agentsData.data || {}).profiles || {};

        const agentNameMap = {};
        for (const [key, val] of Object.entries(agentProfiles)) {
            agentNameMap[key] = val.name || key;
        }

        const queries = (analytics.queries || []).filter(q => q && q.agent !== undefined);
        const totalQueries = metrics.requests || queries.length;
        const totalErrors = metrics.errors || 0;
        const vectorized = vector.total || 0;
        const pendingV = vector.pending || 0;
        const errorRate = totalQueries > 0 ? ((totalErrors / totalQueries) * 100).toFixed(1) : '0.0';
        const avgLatency = queries.length > 0
            ? (queries.reduce((s, q) => s + (q.latency_ms || 0), 0) / queries.length).toFixed(0)
            : '—';
        const vecConvs = state.lastVectorizeResult ? state.lastVectorizeResult.conversations : 0;
        const vecRemaining = state.lastVectorizeResult ? state.lastVectorizeResult.remaining : '—';

        document.getElementById('analytics-kpis').innerHTML = `
            <div class="analytics-card"><div class="value">${totalQueries}</div><div class="label">Requêtes totales</div></div>
            <div class="analytics-card"><div class="value">${errorRate}%</div><div class="label">Taux d'erreur</div></div>
            <div class="analytics-card"><div class="value">${avgLatency}</div><div class="label">Latence moyenne (ms)</div></div>
            <div class="analytics-card"><div class="value">${vectorized}</div><div class="label">Documents vectorisés</div></div>
            <div class="analytics-card"><div class="value">${pendingV}</div><div class="label">En attente d'embedding</div></div>
            <div class="analytics-card"><div class="value">${vecConvs}</div><div class="label">Conversations vectorisées</div></div>
            <div class="analytics-card"><div class="value">${vecRemaining}</div><div class="label">Restantes</div></div>
            <div class="analytics-card"><div class="value">${metrics.pipeline_runs || 0}</div><div class="label">Pipelines exécutés</div></div>
        `;

        const agentCounts = {};
        const agentLatencies = {};
        queries.forEach(q => {
            const agent = q.agent || 'inconnu';
            agentCounts[agent] = (agentCounts[agent] || 0) + 1;
            if (!agentLatencies[agent]) agentLatencies[agent] = [];
            agentLatencies[agent].push(q.latency_ms || 0);
        });

        const agentKeys = Object.keys(agentCounts);
        const agentLabels = agentKeys.map(k => agentNameMap[k] || k);
        const agentData = agentKeys.map(k => agentCounts[k]);
        const agentColors = ['#00d4ff', '#7b2ff7', '#ffaa00', '#00ff88', '#ff4444', '#888'];

        if (typeof Chart !== 'undefined' && agentLabels.length) {
            updateOrCreateChart('chart-agent', 'doughnut', agentLabels, [{ data: agentData, backgroundColor: agentColors, borderWidth: 0 }], { responsive: true, maintainAspectRatio: true, plugins: { legend: { position: 'bottom', labels: { color: '#888', font: { size: 10 } } } } });

            const avgLatPerAgent = agentKeys.map(k => {
                const vals = agentLatencies[k];
                return vals.length ? (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(0) : 0;
            });
            updateOrCreateChart('chart-latency', 'bar', agentLabels, [{ label: 'ms', data: avgLatPerAgent, backgroundColor: '#004466', borderRadius: 4 }], { responsive: true, maintainAspectRatio: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { color: '#666' } }, x: { ticks: { color: '#888', font: { size: 10 } } } } });
        }

        const hourly = new Array(24).fill(0);
        queries.forEach(q => {
            const ts = q.ts || q.timestamp;
            if (ts) {
                const h = new Date(ts * 1000).getHours();
                if (h >= 0 && h < 24) hourly[h]++;
            }
        });

        if (typeof Chart !== 'undefined') {
            updateOrCreateChart('chart-hourly', 'bar', Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0') + 'h'), [{ data: hourly, backgroundColor: hourly.map(v => v > 0 ? '#004466' : '#1a1a24'), borderRadius: 2 }], { responsive: true, maintainAspectRatio: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { color: '#666', stepSize: 1 } }, x: { ticks: { color: '#555', font: { size: 9 }, maxRotation: 0 } } } });

            updateOrCreateChart('chart-vector', 'doughnut', ['Vectorisés', 'En attente'], [{ data: [vectorized, pendingV], backgroundColor: ['#00d4ff', '#2a2a3a'], borderWidth: 0 }], { responsive: true, maintainAspectRatio: true, plugins: { legend: { position: 'bottom', labels: { color: '#888', font: { size: 10 } } } } });
        }
    } catch (e) {
        document.getElementById('analytics-kpis').innerHTML = `<div class="analytics-card"><div class="label error-label">Erreur chargement analytics : ${utils.escHtml(e.message)}</div></div>`;
    }
}

// Vectorize conversations button
document.getElementById('btn-vectorize-convs')?.addEventListener('click', async () => {
    const btn = document.getElementById('btn-vectorize-convs');
    const statusEl = document.getElementById('vectorize-status');
    btn.disabled = true;
    btn.textContent = '⏳ Vectorisation en cours...';
    statusEl.textContent = '';

    try {
        const resp = await fetch('/api/vectorize/conversations', { method: 'POST' });
        const data = await resp.json();
        state.lastVectorizeResult = data;

        if (data.conversations > 0) {
            statusEl.textContent = `✅ ${data.conversations} conversation(s) traitee(s), ${data.vectorized} document(s) vectorise(s)`;
            refreshAnalytics();
        } else {
            statusEl.textContent = data.message || '⚠️ Aucune conversation traitee';
        }
    } catch (e) {
        statusEl.textContent = `❌ Erreur : ${e.message}`;
    } finally {
        btn.disabled = false;
        btn.textContent = '⚡ Vectoriser les conversations (lot de 5)';
    }
});

// Ingest document button
document.getElementById('btn-ingest-doc')?.addEventListener('click', async () => {
    const btn = document.getElementById('btn-ingest-doc');
    const statusEl = document.getElementById('ingest-status');
    const nameInput = document.getElementById('doc-name');
    const contentInput = document.getElementById('doc-content');
    const content = contentInput.value.trim();

    if (!content) {
        statusEl.textContent = '⚠️ Veuillez saisir un contenu';
        return;
    }

    btn.disabled = true;
    btn.textContent = '⏳ Ingestion...';
    statusEl.textContent = '';

    try {
        const doc = { text: content };
        const name = nameInput.value.trim();
        if (name) doc.metadata = { title: name };

        const resp = await fetch('/api/ingest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ documents: [doc], source: 'manual' }),
        });
        const data = await resp.json();

        if (data.error) {
            statusEl.textContent = `❌ ${data.error}`;
        } else {
            statusEl.textContent = `✅ ${data.ingested} document(s) ingere(s)`;
            contentInput.value = '';
            if (name) nameInput.value = '';
            refreshAnalytics();
        }
    } catch (e) {
        statusEl.textContent = `❌ Erreur : ${e.message}`;
    } finally {
        btn.disabled = false;
        btn.textContent = '📄 Ingérer le document';
    }
});