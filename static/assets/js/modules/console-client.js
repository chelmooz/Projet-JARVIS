// console-client.js — Couche données de la Console / Palette (zéro DOM).
// Fonctions pures testables : parseCommand, sendCommand, fetchAgents.
// Le rendu (onglet, overlay) vit dans console-tab.js / command-palette.js.

const JARVIS_ENDPOINT = "/api/jarvis";
const AGENTS_ENDPOINT = "/api/agents";
const DEFAULT_TIMEOUT_MS = 30000;

// --- Store mémoire singleton (handoff Palette -> Console) ---
export const consoleStore = {
  lastCommand: null,
  setLast(cmd) {
    this.lastCommand = cmd;
  },
  getLast() {
    return this.lastCommand;
  },
};

// --- Parsing d'une commande `@agent tâche` ---
// Lève une erreur explicite si invalide (jamais de retour silencieux).
export function parseCommand(input) {
  if (typeof input !== "string") {
    throw new Error("Entrée invalide : une chaîne est attendue");
  }
  const match = input.trim().match(/^@(\w+)\s+([\s\S]+)$/);
  if (!match) {
    throw new Error("Commande invalide : utilisez le format « @agent votre tâche »");
  }
  return { agent: match[1], task: match[2] };
}

// --- Résolution d'une liste d'agents depuis le payload /api/agents ---
// Renvoie [{ key, name, model }]. Best-effort : les clés de profil
// (orchestrateur, techlead, devops, designer, datasecu) portent nom + modèle ;
// les clés de routage (cyber, dev, network, hardware, vision) reçoivent un
// libellé générique et modèle null si absent de agent_model_map.
export function agentsFromApi(data) {
  if (!data || typeof data !== "object") return [];
  const profiles = data.profiles || {};
  const modelMap = data.agent_model_map || {};
  const prefixes = Array.isArray(data.routing_prefixes) ? data.routing_prefixes : [];

  return prefixes.map((prefix) => {
    const key = String(prefix).replace(/^@/, "");
    const profile = profiles[key];
    if (profile && typeof profile === "object") {
      return { key, name: profile.name || key, model: modelMap[key] || null };
    }
    return {
      key,
      name: key.charAt(0).toUpperCase() + key.slice(1),
      model: modelMap[key] || null,
    };
  });
}

// --- Récupération des agents (cache HTTP partagé via cachedFetch) ---
export async function fetchAgents(loader) {
  const fetchFn = loader || (await import("./utils.js")).cachedFetch;
  const data = await fetchFn(AGENTS_ENDPOINT);
  return agentsFromApi(data);
}

// --- Envoi d'une commande à /api/jarvis ---
// Normalise 5xx / réseau / timeout en { ok: false, error } — jamais de throw.
export async function sendCommand(parsed, opts = {}) {
  const { agent, task } = parsed;
  if (!agent || !task) {
    return { ok: false, error: "Commande incomplète (agent ou tâche manquant)" };
  }
  const source = opts.source || "console";
  const timeoutMs = opts.timeoutMs || DEFAULT_TIMEOUT_MS;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const resp = await fetch(JARVIS_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task: `@${agent} ${task}`, source }),
      signal: controller.signal,
    });
    if (!resp.ok) {
      let error = `Erreur HTTP ${resp.status}`;
      try {
        const payload = await resp.json();
        if (payload && payload.error) error = payload.error;
      } catch {
        /* corps non-JSON : on garde le message HTTP */
      }
      return { ok: false, error };
    }
    const data = await resp.json();
    return { ok: true, data };
  } catch (err) {
    if (err && err.name === "AbortError") {
      return { ok: false, error: `Délai dépassé (${timeoutMs / 1000} s)` };
    }
    return { ok: false, error: (err && err.message) || "Erreur réseau" };
  } finally {
    clearTimeout(timer);
  }
}

// --- Convenience : parse + validate + send en une passe ---
export async function runCommand(input, opts = {}) {
  let parsed;
  try {
    parsed = parseCommand(input);
  } catch (err) {
    return { ok: false, error: err.message };
  }
  const result = await sendCommand(parsed, opts);
  if (result.ok) {
    consoleStore.setLast({ ...parsed, source: opts.source || "console" });
  }
  return result;
}
