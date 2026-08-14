import { describe, it, expect, beforeEach } from 'vitest';
import { state, resetState } from '../assets/js/modules/state.js';

describe('state', () => {
  it('expose les clés attendues avec leurs valeurs initiales', () => {
    expect(state.APP_VERSION).toBe('5.6');
    expect(state.selectedAgent).toBeNull();
    expect(state.availableModels).toEqual([]);
    expect(state.currentConvId).toBeNull();
    expect(state.convsExpanded).toBe(true);
    expect(state.pendingImage).toBeNull();
    expect(state.isSending).toBe(false);
    expect(state._lastRevisit).toEqual({ id: null, t: 0 });
    expect(state.analyticsCharts).toEqual({});
    expect(state.lastVectorizeResult).toBeNull();
    expect(state.fbHistory).toEqual([]);
    expect(state.apiCache).toBeInstanceOf(Map);
    expect(state.CACHE_TTL).toBe(30000);
  });

  it('est un singleton : mêmes mutations visibles depuis un second import', async () => {
    state.selectedAgent = 'cyber';
    const { state: stateAgain } = await import('../assets/js/modules/state.js');
    expect(stateAgain.selectedAgent).toBe('cyber');
    state.selectedAgent = null;
  });
});

describe('resetState', () => {
  beforeEach(() => {
    state.selectedAgent = 'dev';
    state.availableModels = ['a', 'b'];
    state.currentConvId = 'conv-123';
    state.convsExpanded = false;
    state.pendingImage = 'data:image/png;base64,xx';
    state.isSending = true;
    state._lastRevisit = { id: 'msg-1', t: 42 };
    state.analyticsCharts = { chart1: {} };
    state.lastVectorizeResult = { ok: true };
    state.fbHistory = ['C:/a', 'C:/a/b'];
  });

  it('réinitialise tous les champs mutables couverts', () => {
    resetState();

    expect(state.selectedAgent).toBeNull();
    expect(state.availableModels).toEqual([]);
    expect(state.currentConvId).toBeNull();
    expect(state.convsExpanded).toBe(true);
    expect(state.pendingImage).toBeNull();
    expect(state.isSending).toBe(false);
    expect(state._lastRevisit).toEqual({ id: null, t: 0 });
    expect(state.analyticsCharts).toEqual({});
    expect(state.lastVectorizeResult).toBeNull();
    expect(state.fbHistory).toEqual([]);
  });

  it('ne touche pas aux champs hors périmètre (apiCache, CACHE_TTL, APP_VERSION)', () => {
    state.apiCache.set('k', 'v');
    resetState();

    expect(state.apiCache.get('k')).toBe('v');
    expect(state.CACHE_TTL).toBe(30000);
    expect(state.APP_VERSION).toBe('5.6');
    state.apiCache.clear();
  });
});
