import { describe, it, expect, vi, beforeEach } from 'vitest';
import { parseCommand, sendCommand, runCommand, fetchAgents, agentsFromApi, consoleStore } from '../assets/js/modules/console-client.js';

describe('parseCommand', () => {
  it('parse une commande valide', () => {
    expect(parseCommand('@cyber scan le firewall')).toEqual({ agent: 'cyber', task: 'scan le firewall' });
  });

  it('accepte une tâche multiligne', () => {
    const input = '@dev\nprint("hello")';
    expect(parseCommand(input)).toEqual({ agent: 'dev', task: 'print("hello")' });
  });

  it('lève une erreur explicite si pas de préfixe', () => {
    expect(() => parseCommand('sans agent')).toThrow(/format/);
  });

  it('lève une erreur explicite si tâche vide', () => {
    expect(() => parseCommand('@cyber')).toThrow(/format/);
  });

  it('lève une erreur explicite si entrée non chaîne', () => {
    expect(() => parseCommand(null)).toThrow(/chaîne/);
  });
});

describe('agentsFromApi', () => {
  const payload = {
    profiles: {
      orchestrateur: { name: 'Orchestrateur' },
      techlead: { name: 'Tech Lead Full-Stack' },
    },
    agent_model_map: { orchestrateur: 'model:q4', techlead: 'model:q4b' },
    routing_prefixes: ['@orchestrateur', '@techlead', '@cyber', '@dev'],
  };

  it('mappe chaque préfixe en { key, name, model }', () => {
    const agents = agentsFromApi(payload);
    expect(agents).toContainEqual({ key: 'orchestrateur', name: 'Orchestrateur', model: 'model:q4' });
    expect(agents).toContainEqual({ key: 'techlead', name: 'Tech Lead Full-Stack', model: 'model:q4b' });
  });

  it('libellé générique pour clé de routage sans profil', () => {
    const agents = agentsFromApi(payload);
    expect(agents).toContainEqual({ key: 'cyber', name: 'Cyber', model: null });
  });

  it('retourne [] sur payload invalide', () => {
    expect(agentsFromApi(null)).toEqual([]);
    expect(agentsFromApi({})).toEqual([]);
  });
});

describe('fetchAgents', () => {
  it('utilise le loader fourni et mappe via agentsFromApi', async () => {
    const loader = vi.fn(async () => ({
      profiles: { cyber: { name: 'Data/Secu' } },
      agent_model_map: {},
      routing_prefixes: ['@cyber'],
    }));
    const agents = await fetchAgents(loader);
    expect(loader).toHaveBeenCalledWith('/api/agents');
    expect(agents).toEqual([{ key: 'cyber', name: 'Data/Secu', model: null }]);
  });
});

describe('sendCommand', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('poste la commande préfixée et renvoie { ok, data }', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ response: 'ok', agent: 'cyber' }),
    }));
    vi.stubGlobal('fetch', fetchMock);

    const res = await sendCommand({ agent: 'cyber', task: 'scan' }, { source: 'console' });
    expect(res.ok).toBe(true);
    expect(res.data).toEqual({ response: 'ok', agent: 'cyber' });
    const sent = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(sent).toEqual({ task: '@cyber scan', source: 'console' });
  });

  it('normalise une erreur 5xx en { ok:false, error } sans throw', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ ok: false, status: 500, json: async () => ({ error: 'boom' }) })),
    );
    const res = await sendCommand({ agent: 'dev', task: 'x' });
    expect(res.ok).toBe(false);
    expect(res.error).toBe('boom');
  });

  it('normalise une erreur réseau en { ok:false, error }', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('offline'); }));
    const res = await sendCommand({ agent: 'dev', task: 'x' });
    expect(res.ok).toBe(false);
    expect(res.error).toBe('offline');
  });

  it('normalise un timeout (AbortError) en { ok:false, error }', async () => {
    const abortErr = Object.assign(new Error('aborted'), { name: 'AbortError' });
    vi.stubGlobal('fetch', vi.fn(async () => { throw abortErr; }));
    const res = await sendCommand({ agent: 'dev', task: 'x' }, { timeoutMs: 1 });
    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/Délai/);
  });

  it('rejette une commande incomplète sans appel réseau', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    const res = await sendCommand({ agent: '', task: '' });
    expect(res.ok).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('runCommand', () => {
  it('parse + envoie et stocke lastCommand en cas de succès', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ response: 'r' }) })));
    const res = await runCommand('@vision décrit l’image', { source: 'palette' });
    expect(res.ok).toBe(true);
    expect(consoleStore.getLast()).toEqual({ agent: 'vision', task: 'décrit l’image', source: 'palette' });
  });

  it('renvoie { ok:false, error } sur commande invalide (jamais de throw)', async () => {
    const res = await runCommand('pas de prefixe');
    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/format/);
  });
});
