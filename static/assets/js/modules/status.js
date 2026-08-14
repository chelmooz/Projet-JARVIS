// status.js — SSE Status stream + polling metrics.
// Dépendances : utils.js, state.js

import { state } from './state.js';

function setSide(id, text, cls) {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = `<span class="status-dot dot-${cls}"></span>${text}`;
}

export function connectStatusSSE() {
    if (state.statusEventSource) {
        state.statusEventSource.close();
    }
    state.statusEventSource = new EventSource('/api/status/stream');
    state.statusEventSource.onmessage = (event) => {
        try {
            const s = JSON.parse(event.data);
            const backendDot = s.ollama ? 'ok' : 'warn';
            setSide('st-backend', s.ollama ? 'ollama' : '?', backendDot);
            setSide('st-ollama', s.ollama ? 'OK' : 'HS', s.ollama ? 'ok' : 'err');
            setSide('st-memory', s.memory ? 'OK' : 'ERR', s.memory ? 'ok' : 'err');
            setSide('st-vector', s.vector ? 'OK' : 'ERR', s.vector ? 'ok' : 'err');
            document.dispatchEvent(new CustomEvent('jarvis:status-updated', { detail: s }));
        } catch (e) {
            console.warn('SSE status parse error:', e);
        }
    };
    state.statusEventSource.onerror = () => {
        // EventSource se reconnecte automatiquement
    };
}

export async function pollMetrics() {
    try {
        const m = ((await (await fetch('/api/metrics')).json()).data) || {};
        const rss = m.memory_rss_mb != null ? m.memory_rss_mb + ' MB' : '—';
        document.getElementById('st-rss').textContent = rss;
        document.getElementById('st-requests').textContent = (m.requests || 0).toLocaleString('en-US');
        document.getElementById('st-uptime').textContent = m.uptime_human || '—';
    } catch (e) {
        // Ignore
    }
}

export function updateBadges(agent, model, backend) {
    document.getElementById('current-agent').textContent = agent || '—';
    document.getElementById('current-model').textContent = model || '—';
    const be = document.getElementById('current-backend');
    be.textContent = backend || '—';
    be.className = 'badge badge-backend';
}

export function startStatusPolling() {
    connectStatusSSE();
    pollMetrics();
    setInterval(pollMetrics, 30000);
    // refreshAnalytics interval géré par analytics.js
}