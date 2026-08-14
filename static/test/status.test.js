import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { connectStatusSSE, pollMetrics, updateBadges } from '../assets/js/modules/status.js';
import { state } from '../assets/js/modules/state.js';

function setupDom() {
  document.body.innerHTML = `
    <span id="st-backend"></span>
    <span id="st-ollama"></span>
    <span id="st-memory"></span>
    <span id="st-vector"></span>
    <span id="st-rss"></span>
    <span id="st-requests"></span>
    <span id="st-uptime"></span>
    <span id="current-agent"></span>
    <span id="current-model"></span>
    <span id="current-backend"></span>
  `;
}

class FakeEventSource {
  constructor(url) {
    this.url = url;
    this.onmessage = null;
    this.onerror = null;
    this.closed = false;
    FakeEventSource.instances.push(this);
  }
  close() {
    this.closed = true;
  }
  emit(data) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
}
FakeEventSource.instances = [];

describe('connectStatusSSE', () => {
  beforeEach(() => {
    setupDom();
    FakeEventSource.instances = [];
    global.EventSource = FakeEventSource;
    state.statusEventSource = null;
  });
  afterEach(() => {
    document.body.innerHTML = '';
    state.statusEventSource = null;
  });

  it('ouvre une connexion vers /api/status/stream', () => {
    connectStatusSSE();
    expect(state.statusEventSource).toBeInstanceOf(FakeEventSource);
    expect(state.statusEventSource.url).toBe('/api/status/stream');
  });

  it('ferme une connexion existante avant d’en ouvrir une nouvelle', () => {
    connectStatusSSE();
    const first = state.statusEventSource;
    connectStatusSSE();
    expect(first.closed).toBe(true);
    expect(state.statusEventSource).not.toBe(first);
  });

  it('un message avec tous les services OK met à jour les badges en "ok"', () => {
    connectStatusSSE();
    state.statusEventSource.emit({ ollama: true, memory: true, vector: true });

    expect(document.getElementById('st-backend').innerHTML).toContain('dot-ok');
    expect(document.getElementById('st-ollama').innerHTML).toContain('OK');
    expect(document.getElementById('st-memory').innerHTML).toContain('dot-ok');
    expect(document.getElementById('st-vector').innerHTML).toContain('dot-ok');
  });

  it('un service en panne (ollama false) affiche warn/err/HS', () => {
    connectStatusSSE();
    state.statusEventSource.emit({ ollama: false, memory: false, vector: false });

    expect(document.getElementById('st-backend').innerHTML).toContain('dot-warn');
    expect(document.getElementById('st-ollama').innerHTML).toContain('HS');
    expect(document.getElementById('st-ollama').innerHTML).toContain('dot-err');
    expect(document.getElementById('st-memory').innerHTML).toContain('ERR');
    expect(document.getElementById('st-vector').innerHTML).toContain('ERR');
  });

  it('émet un événement jarvis:status-updated avec le détail', () => {
    connectStatusSSE();
    const handler = vi.fn();
    document.addEventListener('jarvis:status-updated', handler);

    state.statusEventSource.emit({ ollama: true, memory: true, vector: true });

    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler.mock.calls[0][0].detail).toEqual({ ollama: true, memory: true, vector: true });
  });

  it('un message JSON invalide ne plante pas (catch silencieux)', () => {
    connectStatusSSE();
    expect(() => state.statusEventSource.onmessage({ data: 'not json' })).not.toThrow();
  });

  it('un élément DOM manquant ne plante pas setSide', () => {
    document.getElementById('st-backend').remove();
    connectStatusSSE();
    expect(() => state.statusEventSource.emit({ ollama: true, memory: true, vector: true })).not.toThrow();
  });
});

describe('pollMetrics', () => {
  beforeEach(() => {
    setupDom();
  });
  afterEach(() => {
    document.body.innerHTML = '';
    vi.restoreAllMocks();
  });

  it('affiche les métriques formatées (rss, requests, uptime)', async () => {
    global.fetch = vi.fn(async () => ({
      json: async () => ({ data: { memory_rss_mb: 128, requests: 4200, uptime_human: '2h 30m' } }),
    }));

    await pollMetrics();

    expect(document.getElementById('st-rss').textContent).toBe('128 MB');
    expect(document.getElementById('st-requests').textContent).toBe('4,200');
    expect(document.getElementById('st-uptime').textContent).toBe('2h 30m');
  });

  it('affiche des tirets si les métriques sont absentes', async () => {
    global.fetch = vi.fn(async () => ({ json: async () => ({ data: {} }) }));

    await pollMetrics();

    expect(document.getElementById('st-rss').textContent).toBe('—');
    expect(document.getElementById('st-requests').textContent).toBe('0');
    expect(document.getElementById('st-uptime').textContent).toBe('—');
  });

  it('une erreur réseau est ignorée silencieusement', async () => {
    global.fetch = vi.fn(async () => {
      throw new Error('network down');
    });

    await expect(pollMetrics()).resolves.toBeUndefined();
  });
});

describe('updateBadges', () => {
  beforeEach(() => setupDom());
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('affiche agent / modèle / backend', () => {
    updateBadges('cyber', 'llama3', 'ollama');

    expect(document.getElementById('current-agent').textContent).toBe('cyber');
    expect(document.getElementById('current-model').textContent).toBe('llama3');
    expect(document.getElementById('current-backend').textContent).toBe('ollama');
  });

  it('affiche des tirets pour les valeurs absentes', () => {
    updateBadges(null, undefined, '');

    expect(document.getElementById('current-agent').textContent).toBe('—');
    expect(document.getElementById('current-model').textContent).toBe('—');
    expect(document.getElementById('current-backend').textContent).toBe('—');
  });
});
