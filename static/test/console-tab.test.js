import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ConsoleTab } from '../assets/js/modules/console-tab.js';

function setupDom() {
  document.body.innerHTML = `
    <div class="tab-content" id="tab-console">
      <span class="badge" id="console-conn">—</span>
      <div class="console-scrollback" id="console-scrollback"></div>
      <textarea id="console-input"></textarea>
      <button id="console-send-btn"></button>
    </div>`;
}

describe('ConsoleTab', () => {
  let tab;

  beforeEach(() => {
    setupDom();
    localStorage.clear();
    tab = new ConsoleTab();
    tab.mount();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = '';
  });

  it('append une commande puis la réponse dans le scrollback', async () => {
    global.fetch = vi.fn(async () => ({ ok: true, json: async () => ({ response: 'rép', agent: 'cyber' }) }));
    tab.input.value = '@cyber scan';
    await tab.submit();

    const rows = tab.scrollback.querySelectorAll('.console-row');
    expect(rows.length).toBe(2);
    expect(rows[0].className).toContain('console-row-command');
    expect(rows[0].textContent).toContain('@cyber');
    expect(rows[1].textContent).toContain('rép');
  });

  it('affiche une erreur si commande invalide (jamais de throw)', async () => {
    tab.input.value = 'pas de prefixe';
    await tab.submit();
    const rows = tab.scrollback.querySelectorAll('.console-row');
    expect(rows.length).toBe(1);
    expect(rows[0].className).toContain('console-row-error');
    expect(rows[0].textContent).toMatch(/format/);
  });

  it('affiche l’erreur réseau sans planter', async () => {
    global.fetch = vi.fn(async () => { throw new Error('offline'); });
    tab.input.value = '@dev fais';
    await tab.submit();
    expect(tab.scrollback.textContent).toContain('offline');
  });

  it('historique : ArrowUp rappelle la dernière commande', () => {
    tab._pushHistory('@cyber a');
    tab._pushHistory('@dev b');
    tab.input.value = '';
    tab._historyNav(-1);
    expect(tab.input.value).toBe('@dev b');
    tab._historyNav(-1);
    expect(tab.input.value).toBe('@cyber a');
    tab._historyNav(1);
    expect(tab.input.value).toBe('@dev b');
  });

  it('historique : persisté dans localStorage (commandes seules)', async () => {
    global.fetch = vi.fn(async () => ({ ok: true, json: async () => ({ response: 'x' }) }));
    tab.input.value = '@cyber persist';
    await tab.submit();
    const stored = JSON.parse(localStorage.getItem('jarvis_console_history'));
    expect(stored).toContain('@cyber persist');
  });

  it('handoff : envoie la commande en Console (sans crash si tab absent)', () => {
    const tabBtn = document.createElement('button');
    tabBtn.className = 'tab-btn';
    tabBtn.dataset.tab = 'console';
    document.body.appendChild(tabBtn);
    tab._onHandoff({ agent: 'vision', task: 'decris' });
    expect(tab.scrollback.textContent).toContain('@vision decris');
  });

  it('statut : maj du badge via jarvis:status-updated', () => {
    tab._onStatus({ ollama: true });
    expect(tab.connBadge.textContent).toBe('connecté');
    tab._onStatus({ ollama: false });
    expect(tab.connBadge.textContent).toBe('hors-ligne');
  });
});
