// state.js — État partagé du frontend (singleton mutable).
// Un seul objet exporté pour éviter les variables globales dispersées.

export const state = {
    // App
    APP_VERSION: '5.6',

    // Chat
    selectedAgent: null,
    availableModels: [],
    currentConvId: null,
    convsExpanded: true,
    pendingImage: null,
    isSending: false,

    // Feedback / revisit
    _lastRevisit: { id: null, t: 0 },

    // Status / metrics
    statusEventSource: null,
    analyticsCharts: {},
    lastVectorizeResult: null,

    // Cache
    apiCache: new Map(),
    CACHE_TTL: 30000,

    // Chart.js
    chartJsLoaded: false,

    // File browser
    fbHistory: [],

    // DOM elements (cachés après init)
    chat: null,
    input: null,
    sendBtn: null,
};

// Helper pour réinitialiser l'état si nécessaire (tests, etc.)
export function resetState() {
    state.selectedAgent = null;
    state.availableModels = [];
    state.currentConvId = null;
    state.convsExpanded = true;
    state.pendingImage = null;
    state.isSending = false;
    state._lastRevisit = { id: null, t: 0 };
    state.analyticsCharts = {};
    state.lastVectorizeResult = null;
    state.fbHistory = [];
}