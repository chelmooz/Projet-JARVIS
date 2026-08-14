import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  closeBrowser,
  openBrowser,
  browseDir,
  browserGoUp,
  browserSelect,
  authorizePath,
  revokePath,
  refreshPathAuth,
} from '../assets/js/modules/files.js';
import { state } from '../assets/js/modules/state.js';

function setupDom() {
  document.body.innerHTML = `
    <div id="fb-overlay" class="">
      <div class="fb-modal">
        <button id="fb-close">close</button>
        <span id="fb-breadcrumb"></span>
        <button id="fb-back" style="display:none"></button>
        <input id="fb-path" />
        <div id="fb-body"></div>
        <button id="fb-cancel-btn">cancel</button>
        <button id="fb-select-btn">select</button>
      </div>
    </div>
    <input id="fp-path" />
    <span id="fp-feedback" class="fp-feedback"></span>
    <div id="fp-list"></div>
    <button id="fp-browse"></button>
  `;
}

describe('closeBrowser / openBrowser', () => {
  beforeEach(() => {
    setupDom();
    global.fetch = vi.fn(async () => ({ json: async () => ({ drives: [] }) }));
  });
  afterEach(() => {
    document.body.innerHTML = '';
    vi.restoreAllMocks();
  });

  it('openBrowser affiche la modale et réinitialise fbHistory', () => {
    state.fbHistory = ['C:/old'];
    openBrowser();

    expect(document.getElementById('fb-overlay').classList.contains('show')).toBe(true);
    expect(state.fbHistory).toEqual([]);
  });

  it('closeBrowser masque la modale et vide fbHistory', () => {
    openBrowser();
    state.fbHistory = ['C:/a'];

    closeBrowser();

    expect(document.getElementById('fb-overlay').classList.contains('show')).toBe(false);
    expect(state.fbHistory).toEqual([]);
  });

  it('openBrowser restaure le focus au ferme (dernier élément actif)', () => {
    const trigger = document.getElementById('fp-browse');
    trigger.focus();
    openBrowser();
    closeBrowser();

    expect(document.activeElement).toBe(trigger);
  });
});

describe('browseDir (loadDrives via fetch)', () => {
  beforeEach(() => {
    setupDom();
  });
  afterEach(() => {
    document.body.innerHTML = '';
    vi.restoreAllMocks();
  });

  it('liste les entrées retournées et affiche le breadcrumb', async () => {
    global.fetch = vi.fn(async () => ({
      json: async () => ({ entries: [{ name: 'Documents', path: 'C:/Documents' }] }),
    }));

    await browseDir('C:/Documents');

    const body = document.getElementById('fb-body');
    expect(body.querySelectorAll('.fb-folder').length).toBe(1);
    expect(body.textContent).toContain('Documents');
    expect(document.getElementById('fb-back').style.display).toBe('inline-block');
  });

  it('dossier vide affiche un message dédié', async () => {
    global.fetch = vi.fn(async () => ({ json: async () => ({ entries: [] }) }));

    await browseDir('C:/Empty');

    expect(document.getElementById('fb-body').textContent).toContain('Dossier vide ou inaccessible');
  });

  it('erreur réseau affiche un message échappé, ne plante pas', async () => {
    global.fetch = vi.fn(async () => {
      throw new Error('<boom>');
    });

    await expect(browseDir('C:/x')).resolves.toBeUndefined();
    expect(document.getElementById('fb-body').innerHTML).toContain('&lt;boom&gt;');
  });

  it('empile le chemin dans state.fbHistory', async () => {
    global.fetch = vi.fn(async () => ({ json: async () => ({ entries: [] }) }));
    state.fbHistory = [];

    await browseDir('C:/a');
    await browseDir('C:/a/b');

    expect(state.fbHistory).toEqual(['C:/a', 'C:/a/b']);
  });
});

describe('browserGoUp', () => {
  beforeEach(() => {
    setupDom();
    global.fetch = vi.fn(async () => ({ json: async () => ({ entries: [], drives: [] }) }));
  });
  afterEach(() => {
    document.body.innerHTML = '';
    vi.restoreAllMocks();
    state.fbHistory = [];
  });

  it('avec un seul élément dans l’historique, remonte aux lecteurs', () => {
    state.fbHistory = ['C:/a'];
    browserGoUp();
    expect(state.fbHistory).toEqual(['C:/a']);
  });

  it('avec plusieurs éléments, retire le dernier puis navigue au précédent (qui se réempile)', () => {
    state.fbHistory = ['C:/a', 'C:/a/b'];
    browserGoUp();
    // pop() retire 'C:/a/b' -> ['C:/a'], puis browseDir('C:/a') réempile 'C:/a'
    expect(state.fbHistory).toEqual(['C:/a', 'C:/a']);
  });
});

describe('browserSelect', () => {
  beforeEach(() => {
    setupDom();
    global.fetch = vi.fn(async () => ({ json: async () => ({ success: true }) }));
  });
  afterEach(() => {
    document.body.innerHTML = '';
    vi.restoreAllMocks();
  });

  it('sans chemin saisi, ne fait rien', () => {
    document.getElementById('fb-path').value = '';
    expect(() => browserSelect()).not.toThrow();
  });

  it('avec un chemin, le reporte dans fp-path, ferme la modale, et lance authorizePath', async () => {
    document.getElementById('fb-path').value = 'C:/chosen';
    browserSelect();

    expect(document.getElementById('fb-overlay').classList.contains('show')).toBe(false);
    // authorizePath() est déclenché sans await : on laisse ses microtasks se résoudre
    await vi.waitFor(() => expect(document.getElementById('fp-path').value).toBe(''));
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/files/authorize',
      expect.objectContaining({ body: JSON.stringify({ path: 'C:/chosen' }) })
    );
  });
});

describe('authorizePath', () => {
  beforeEach(() => setupDom());
  afterEach(() => {
    document.body.innerHTML = '';
    vi.restoreAllMocks();
  });

  it('succès : affiche un feedback positif', async () => {
    global.fetch = vi.fn(async () => ({ json: async () => ({ success: true }) }));

    await authorizePath('C:/ok');

    const fb = document.getElementById('fp-feedback');
    expect(fb.className).toContain('ok');
    expect(fb.textContent).toContain('C:/ok');
  });

  it('échec métier : affiche le message d’erreur retourné', async () => {
    global.fetch = vi.fn(async () => ({ json: async () => ({ success: false, error: 'chemin invalide' }) }));

    await authorizePath('C:/bad');

    const fb = document.getElementById('fp-feedback');
    expect(fb.className).toContain('err');
    expect(fb.textContent).toContain('chemin invalide');
  });

  it('erreur réseau : affiche un message réseau', async () => {
    global.fetch = vi.fn(async () => {
      throw new Error('down');
    });

    await authorizePath('C:/x');

    const fb = document.getElementById('fp-feedback');
    expect(fb.className).toContain('err');
    expect(fb.textContent).toContain('down');
  });

  it('sans chemin (ni argument ni input), ne fait rien', async () => {
    document.getElementById('fp-path').value = '  ';
    global.fetch = vi.fn();

    await authorizePath();

    expect(global.fetch).not.toHaveBeenCalled();
  });
});

describe('revokePath', () => {
  beforeEach(() => setupDom());
  afterEach(() => {
    document.body.innerHTML = '';
    vi.restoreAllMocks();
  });

  it('succès : affiche un feedback de révocation', async () => {
    global.fetch = vi.fn(async () => ({ json: async () => ({ success: true }) }));

    await revokePath('C:/revoked');

    const fb = document.getElementById('fp-feedback');
    expect(fb.className).toContain('ok');
    expect(fb.textContent).toContain('C:/revoked');
  });

  it('échec : affiche le message d’erreur', async () => {
    global.fetch = vi.fn(async () => ({ json: async () => ({ success: false, error: 'introuvable' }) }));

    await revokePath('C:/missing');

    const fb = document.getElementById('fp-feedback');
    expect(fb.className).toContain('err');
    expect(fb.textContent).toContain('introuvable');
  });
});

describe('refreshPathAuth', () => {
  beforeEach(() => setupDom());
  afterEach(() => {
    document.body.innerHTML = '';
    vi.restoreAllMocks();
  });

  it('affiche la liste des chemins autorisés', async () => {
    global.fetch = vi.fn(async () => ({ json: async () => ({ paths: ['C:/a', 'C:/b'] }) }));

    await refreshPathAuth();

    const rows = document.querySelectorAll('#fp-list .path-row');
    expect(rows.length).toBe(2);
  });

  it('liste vide : affiche un message dédié', async () => {
    global.fetch = vi.fn(async () => ({ json: async () => ({ paths: [] }) }));

    await refreshPathAuth();

    expect(document.getElementById('fp-list').textContent).toContain('Aucun dossier autorise');
  });

  it('erreur réseau : ne plante pas', async () => {
    global.fetch = vi.fn(async () => {
      throw new Error('down');
    });

    await expect(refreshPathAuth()).resolves.toBeUndefined();
  });
});
