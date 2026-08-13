// utils.js — Utilitaires partagés (pas d'état, pas d'effets de bord).
// Exportés pour être importés par les autres modules.

// --- HTML escape pour données API non fiables ---
export function escHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

// --- Debounce utility ---
export function debounce(fn, delay) {
    let timeoutId;
    return function (...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn.apply(this, args), delay);
    };
}

// --- Toast notifications ---
export function toast(msg, type = 'info') {
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = 'toast ' + type;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => {
        el.classList.add('removing');
        setTimeout(() => el.remove(), 300);
    }, 3000);
}

// --- Markdown renderer (Fixé & Sécurisé) ---
export function renderMarkdown(text) {
    if (!text) return '';
    let safe = escHtml(text);
    safe = safe.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
        return `<pre><code class="language-${lang || 'plaintext'}">${code}</code></pre>`;
    });
    safe = safe.replace(/`([^`]+)`/g, '<code>$1</code>');
    safe = safe.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    safe = safe.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    safe = safe.replace(/^### (.+)$/gm, '<h4>$1</h4>');
    safe = safe.replace(/^## (.+)$/gm, '<h3>$1</h3>');
    safe = safe.replace(/^# (.+)$/gm, '<h2>$1</h2>');
    safe = safe.replace(/\n/g, '<br>');
    return safe;
}

// --- Skeleton Loaders ---
export function buildSkeletonCard() {
    return `<div class="skeleton-card">
        <div class="skeleton-row">
            <div class="skeleton skeleton-emoji"></div>
            <div class="skeleton-col">
                <div class="skeleton skeleton-line h-18 w-60"></div>
                <div class="skeleton skeleton-line w-40"></div>
            </div>
        </div>
        <div class="skeleton skeleton-line w-80"></div>
        <div class="skeleton skeleton-line w-60"></div>
    </div>`;
}

export function injectSkeletons(grid, count) {
    if (!grid) return;
    grid.innerHTML = Array.from({ length: count }, buildSkeletonCard).join('');
}

// --- Chart.js lazy loading ---
let chartJsLoaded = false;

export async function loadChartJs() {
    if (chartJsLoaded) return;
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = 'assets/js/chart.umd.min.js';
        script.onload = () => {
            chartJsLoaded = true;
            resolve();
        };
        script.onerror = () => reject(new Error('Failed to load Chart.js'));
        document.head.appendChild(script);
    });
}

// --- Auto-resize textarea ---
export function autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

// --- Client-side cache with TTL ---
export const apiCache = new Map();
export const CACHE_TTL = 30000; // 30 seconds

export async function cachedFetch(url) {
    const now = Date.now();
    const cached = apiCache.get(url);
    if (cached && now - cached.timestamp < CACHE_TTL) {
        return cached.data;
    }
    const resp = await fetch(url);
    const data = await resp.json();
    apiCache.set(url, { data, timestamp: now });
    return data;
}