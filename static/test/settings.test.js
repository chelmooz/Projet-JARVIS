import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  getTheme,
  setTheme,
  toggleTheme,
  initThemeToggle,
  applyOfflineState,
  restoreSettings,
} from '../assets/js/modules/settings.js';
import { state } from '../assets/js/modules/state.js';

function setupDom() {
  document.body.innerHTML = `
    <div class="main"></div>
    <button id="theme-toggle" aria-pressed="false"><span class="icon"></span></button>
    <textarea id="chat-input"></textarea>
    <input id="s-offline" type="checkbox" />
    <input id="s-default-model" />
  `;
}

describe('getTheme / setTheme', () => {
  beforeEach(() => {
    setupDom();
    localStorage.clear();
  });
  afterEach(() => {
    document.body.innerHTML = '';
    localStorage.clear();
  });

  it('getTheme retourne "dark" par défaut', () => {
    expect(getTheme()).toBe('dark');
  });

  it('getTheme retourne la valeur persistée', () => {
    localStorage.setItem('jarvis_theme', 'light');
    expect(getTheme()).toBe('light');
  });

  it('setTheme applique l’attribut data-theme et persiste', () => {
    setTheme('light');

    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(localStorage.getItem('jarvis_theme')).toBe('light');
  });

  it('setTheme met à jour le bouton (aria-pressed + icône)', () => {
    setTheme('light');
    const btn = document.getElementById('theme-toggle');
    expect(btn.getAttribute('aria-pressed')).toBe('true');
    expect(btn.querySelector('.icon').textContent).toBe('☀️');

    setTheme('dark');
    expect(btn.getAttribute('aria-pressed')).toBe('false');
    expect(btn.querySelector('.icon').textContent).toBe('🌙');
  });

  it('setTheme ne plante pas si le bouton est absent', () => {
    document.getElementById('theme-toggle').remove();
    expect(() => setTheme('light')).not.toThrow();
  });
});

describe('toggleTheme', () => {
  beforeEach(() => {
    setupDom();
    localStorage.clear();
  });
  afterEach(() => {
    document.body.innerHTML = '';
    localStorage.clear();
  });

  it('bascule dark -> light -> dark', () => {
    setTheme('dark');
    toggleTheme();
    expect(getTheme()).toBe('light');
    toggleTheme();
    expect(getTheme()).toBe('dark');
  });
});

describe('initThemeToggle', () => {
  beforeEach(() => {
    setupDom();
    localStorage.clear();
  });
  afterEach(() => {
    document.body.innerHTML = '';
    localStorage.clear();
  });

  it('applique le thème courant et attache le clic pour basculer', () => {
    localStorage.setItem('jarvis_theme', 'light');
    initThemeToggle();

    expect(document.documentElement.getAttribute('data-theme')).toBe('light');

    document.getElementById('theme-toggle').click();
    expect(getTheme()).toBe('dark');
  });

  it('ne plante pas si le bouton est absent', () => {
    document.getElementById('theme-toggle').remove();
    expect(() => initThemeToggle()).not.toThrow();
  });
});

describe('applyOfflineState', () => {
  beforeEach(() => {
    setupDom();
    state.sendBtn = null;
  });
  afterEach(() => {
    document.body.innerHTML = '';
    state.sendBtn = null;
  });

  it('crée la bannière hors-ligne si absente, et l’affiche quand offline=true', () => {
    applyOfflineState(true);

    const banner = document.getElementById('offline-banner');
    expect(banner).not.toBeNull();
    expect(banner.style.display).toBe('block');
  });

  it('réutilise la bannière existante (ne la duplique pas)', () => {
    applyOfflineState(true);
    applyOfflineState(true);

    expect(document.querySelectorAll('#offline-banner').length).toBe(1);
  });

  it('masque la bannière quand offline=false', () => {
    applyOfflineState(true);
    applyOfflineState(false);

    expect(document.getElementById('offline-banner').style.display).toBe('none');
  });

  it('change le placeholder du chat selon le mode', () => {
    applyOfflineState(true);
    expect(document.getElementById('chat-input').placeholder).toContain('hors-ligne');

    applyOfflineState(false);
    expect(document.getElementById('chat-input').placeholder).toContain('Posez votre question');
  });

  it('désactive state.sendBtn quand offline=true', () => {
    state.sendBtn = document.createElement('button');
    applyOfflineState(true);
    expect(state.sendBtn.disabled).toBe(true);

    applyOfflineState(false);
    expect(state.sendBtn.disabled).toBe(false);
  });
});

describe('restoreSettings', () => {
  beforeEach(() => {
    setupDom();
    localStorage.clear();
  });
  afterEach(() => {
    document.body.innerHTML = '';
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('applique les préférences renvoyées par /api/settings', async () => {
    global.fetch = vi.fn(async () => ({ json: async () => ({ offline: true }) }));

    await restoreSettings();

    expect(document.getElementById('s-offline').checked).toBe(true);
    expect(localStorage.getItem('jarvis_offline')).toBe('true');
    expect(document.getElementById('offline-banner').style.display).toBe('block');
  });

  it('en cas d’échec réseau, retombe sur le localStorage', async () => {
    localStorage.setItem('jarvis_offline', 'true');
    global.fetch = vi.fn(async () => {
      throw new Error('down');
    });

    await restoreSettings();

    expect(document.getElementById('s-offline').checked).toBe(true);
  });

  it('restaure le modèle par défaut depuis le localStorage', async () => {
    localStorage.setItem('jarvis_default_model', 'llama3');
    global.fetch = vi.fn(async () => ({ json: async () => ({}) }));

    await restoreSettings();

    expect(document.getElementById('s-default-model').value).toBe('llama3');
  });
});
