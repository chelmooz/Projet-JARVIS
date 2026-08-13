import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { CommandPalette } from '../assets/js/modules/command-palette.js';

function setupAgentsResponse() {
  global.fetch = vi.fn(async (url) => {
    if (url === '/api/agents') {
      return {
        ok: true,
        json: async () => ({
          profiles: { cyber: { name: 'Data/Secu' }, dev: { name: 'Tech Lead' } },
          agent_model_map: { cyber: 'm:cyber' },
          routing_prefixes: ['@cyber', '@dev'],
        }),
      };
    }
    return { ok: true, json: async () => ({ response: 'réponse agent', agent: 'cyber' }) };
  });
}

describe('CommandPalette', () => {
  let palette;

  beforeEach(async () => {
    setupAgentsResponse();
    palette = new CommandPalette();
    await palette.mount();
  });

  afterEach(() => {
    if (palette.overlay && palette.overlay.parentNode) palette.overlay.parentNode.removeChild(palette.overlay);
    vi.restoreAllMocks();
  });

  it('open() affiche l’overlay et focus l’input', () => {
    expect(palette.isOpen()).toBe(false);
    palette.open();
    expect(palette.isOpen()).toBe(true);
    expect(document.activeElement).toBe(palette.input);
  });

  it('close() masque l’overlay et vide le champ', () => {
    palette.open();
    palette.input.value = '@cyber test';
    palette.close();
    expect(palette.isOpen()).toBe(false);
    expect(palette.input.value).toBe('');
  });

  it('toggle() bascule l’état', () => {
    palette.toggle();
    expect(palette.isOpen()).toBe(true);
    palette.toggle();
    expect(palette.isOpen()).toBe(false);
  });

  it('autocomplétion : filtre les agents sur préfixe @cy', async () => {
    palette.open();
    palette.input.value = '@cy';
    palette._onInput();
    const items = palette.suggestions.querySelectorAll('.palette-suggestion');
    expect(items.length).toBe(1);
    expect(items[0].dataset.agent).toBe('cyber');
  });

  it('autocomplétion : aucune suggestion sans saisie', () => {
    palette.open();
    palette._renderSuggestions('');
    expect(palette.suggestions.children.length).toBe(0);
  });

  it('submit() poste avec source=palette et affiche la réponse', async () => {
    palette.open();
    palette.input.value = '@cyber scan';
    await palette.submit();
    expect(palette.result.innerHTML).toContain('réponse agent');
    const body = JSON.parse(global.fetch.mock.calls.find((c) => c[0] === '/api/jarvis')[1].body);
    expect(body).toEqual({ task: '@cyber scan', source: 'palette' });
  });

  it('submit() affiche l’erreur en cas d’échec', async () => {
    global.fetch = vi.fn(async (url) =>
      url === '/api/agents'
        ? { ok: true, json: async () => ({ profiles: {}, agent_model_map: {}, routing_prefixes: [] }) }
        : { ok: false, status: 500, json: async () => ({ error: 'KO' }) },
    );
    palette.open();
    palette.input.value = '@cyber scan';
    await palette.submit();
    expect(palette.result.innerHTML).toContain('KO');
  });

  it('Escape ferme la palette', () => {
    palette.open();
    palette.input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(palette.isOpen()).toBe(false);
  });

  it('handoff() émet jarvis:palette-handoff et stocke la commande', () => {
    const handler = vi.fn();
    document.addEventListener('jarvis:palette-handoff', handler);
    palette.open();
    palette.input.value = '@dev écris un script';
    palette.handoff();
    expect(handler).toHaveBeenCalled();
    const detail = handler.mock.calls[0][0].detail;
    expect(detail).toEqual({ agent: 'dev', task: 'écris un script' });
    expect(palette.isOpen()).toBe(false);
  });
});
