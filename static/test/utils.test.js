import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  escHtml,
  debounce,
  toast,
  renderMarkdown,
  buildSkeletonCard,
  injectSkeletons,
  autoResize,
  apiCache,
  CACHE_TTL,
  cachedFetch,
} from '../assets/js/modules/utils.js';

describe('escHtml', () => {
  it('échappe les caractères HTML dangereux', () => {
    expect(escHtml('<script>alert(1)</script>')).toBe('&lt;script&gt;alert(1)&lt;/script&gt;');
  });

  it('laisse le texte simple inchangé', () => {
    expect(escHtml('bonjour')).toBe('bonjour');
  });
});

describe('debounce', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("n'appelle la fonction qu'une fois après le délai, malgré plusieurs appels rapprochés", () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced('a');
    debounced('b');
    debounced('c');
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith('c');
  });
});

describe('toast', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    document.body.innerHTML = '<div id="toast-container"></div>';
  });
  afterEach(() => {
    vi.useRealTimers();
    document.body.innerHTML = '';
  });

  it('ajoute un toast avec le bon message et type', () => {
    toast('Sauvegardé', 'success');
    const el = document.querySelector('#toast-container .toast');
    expect(el).not.toBeNull();
    expect(el.textContent).toBe('Sauvegardé');
    expect(el.className).toBe('toast success');
  });

  it('type par défaut = info', () => {
    toast('Un message');
    const el = document.querySelector('#toast-container .toast');
    expect(el.className).toBe('toast info');
  });

  it('se retire automatiquement après le délai', () => {
    toast('Bye');
    expect(document.querySelectorAll('.toast').length).toBe(1);
    vi.advanceTimersByTime(3300);
    expect(document.querySelectorAll('.toast').length).toBe(0);
  });
});

describe('renderMarkdown', () => {
  it('chaîne vide/nulle → chaîne vide', () => {
    expect(renderMarkdown('')).toBe('');
    expect(renderMarkdown(null)).toBe('');
  });

  it('échappe le HTML brut avant transformation (anti-XSS)', () => {
    expect(renderMarkdown('<img src=x onerror=alert(1)>')).not.toContain('<img');
  });

  it('transforme un bloc de code avec langage', () => {
    const out = renderMarkdown('```js\nconst a = 1;\n```');
    expect(out).toContain('<pre><code class="language-js">');
    expect(out).toContain('const a = 1;');
  });

  it('transforme le code inline, le gras et l’italique', () => {
    expect(renderMarkdown('`code`')).toBe('<code>code</code>');
    expect(renderMarkdown('**gras**')).toBe('<strong>gras</strong>');
    expect(renderMarkdown('*italique*')).toBe('<em>italique</em>');
  });

  it('transforme les titres # ## ###', () => {
    expect(renderMarkdown('# Titre')).toBe('<h2>Titre</h2>');
    expect(renderMarkdown('## Sous-titre')).toBe('<h3>Sous-titre</h3>');
    expect(renderMarkdown('### Section')).toBe('<h4>Section</h4>');
  });

  it('convertit les sauts de ligne en <br>', () => {
    expect(renderMarkdown('a\nb')).toBe('a<br>b');
  });
});

describe('buildSkeletonCard / injectSkeletons', () => {
  it('buildSkeletonCard retourne un fragment avec la classe skeleton-card', () => {
    expect(buildSkeletonCard()).toContain('skeleton-card');
  });

  it('injectSkeletons injecte N cartes dans la grille', () => {
    document.body.innerHTML = '<div id="grid"></div>';
    const grid = document.getElementById('grid');
    injectSkeletons(grid, 3);
    expect(grid.querySelectorAll('.skeleton-card').length).toBe(3);
  });

  it('injectSkeletons ne plante pas si la grille est absente', () => {
    expect(() => injectSkeletons(null, 3)).not.toThrow();
  });
});

describe('autoResize', () => {
  it('fixe la hauteur en fonction de scrollHeight, plafonnée à 120px', () => {
    const el = document.createElement('textarea');
    Object.defineProperty(el, 'scrollHeight', { value: 250, configurable: true });
    autoResize(el);
    expect(el.style.height).toBe('120px');
  });

  it("n'applique pas de plafond si scrollHeight est sous 120px", () => {
    const el = document.createElement('textarea');
    Object.defineProperty(el, 'scrollHeight', { value: 40, configurable: true });
    autoResize(el);
    expect(el.style.height).toBe('40px');
  });
});

describe('cachedFetch', () => {
  beforeEach(() => {
    apiCache.clear();
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('appelle fetch au premier appel puis sert le cache tant que CACHE_TTL n’est pas dépassé', async () => {
    const fetchMock = vi.fn(async () => ({ json: async () => ({ v: 1 }) }));
    global.fetch = fetchMock;

    const first = await cachedFetch('/api/x');
    const second = await cachedFetch('/api/x');

    expect(first).toEqual({ v: 1 });
    expect(second).toEqual({ v: 1 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('re-fetch après expiration du TTL', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ json: async () => ({ v: 1 }) })
      .mockResolvedValueOnce({ json: async () => ({ v: 2 }) });
    global.fetch = fetchMock;

    await cachedFetch('/api/y');
    vi.advanceTimersByTime(CACHE_TTL + 1);
    const second = await cachedFetch('/api/y');

    expect(second).toEqual({ v: 2 });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
