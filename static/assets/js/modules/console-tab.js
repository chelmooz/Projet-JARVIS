// console-tab.js — 9ᵉ onglet SPA : scrollback append-only, historique, statut.
// Délègue l'envoi à console-client.js. Réagit au handoff Palette (MT-5)
// et à l'événement de statut `jarvis:status-updated` (MT-6).

import { escHtml } from "./utils.js";
import { parseCommand, sendCommand, consoleStore } from "./console-client.js";

const HISTORY_KEY = "jarvis_console_history";
const HISTORY_MAX = 50;

export class ConsoleTab {
  constructor() {
    this.scrollback = null;
    this.input = null;
    this.sendBtn = null;
    this.connBadge = null;
    this.history = this._loadHistory();
    this.historyIndex = this.history.length;
    this._mounted = false;
  }

  mount() {
    if (this._mounted) return this;
    this.scrollback = document.getElementById("console-scrollback");
    this.input = document.getElementById("console-input");
    this.sendBtn = document.getElementById("console-send-btn");
    this.connBadge = document.getElementById("console-conn");
    if (!this.scrollback || !this.input || !this.sendBtn) return this;

    this.sendBtn.addEventListener("click", () => this.submit());
    this.input.addEventListener("keydown", (e) => this._onKey(e));

    document.addEventListener("jarvis:palette-handoff", (e) => this._onHandoff(e.detail));
    document.addEventListener("jarvis:status-updated", (e) => this._onStatus(e.detail));

    this._mounted = true;
    return this;
  }

  // --- Soumission ---
  async submit() {
    const raw = this.input.value.trim();
    if (!raw) return;

    let parsed;
    try {
      parsed = parseCommand(raw);
    } catch (err) {
      this._append("error", null, err.message);
      return;
    }

    this._append("command", parsed.agent, raw);
    this._pushHistory(raw);
    this.input.value = "";

    const res = await sendCommand(parsed, { source: "console" });
    if (res.ok) {
      const text = res.data && res.data.response ? res.data.response : JSON.stringify(res.data);
      this._append("response", res.data && res.data.agent ? res.data.agent : parsed.agent, text);
    } else {
      this._append("error", parsed.agent, res.error);
    }
  }

  // --- Scrollback append-only ---
  _append(kind, agent, text) {
    if (!this.scrollback) return;
    const row = document.createElement("div");
    row.className = `console-row console-row-${kind}`;
    if (agent) {
      const badge = document.createElement("span");
      badge.className = "badge badge-agent";
      badge.textContent = `@${agent}`;
      row.appendChild(badge);
    }
    const body = document.createElement("span");
    body.className = "console-text";
    body.textContent = text;
    row.appendChild(body);
    this.scrollback.appendChild(row);
    this.scrollback.scrollTop = this.scrollback.scrollHeight;
  }

  // --- Historique (localStorage, commandes uniquement) ---
  _loadHistory() {
    try {
      const raw = localStorage.getItem(HISTORY_KEY);
      const arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr.slice(-HISTORY_MAX) : [];
    } catch {
      return [];
    }
  }

  _pushHistory(cmd) {
    if (this.history[this.history.length - 1] === cmd) return;
    this.history.push(cmd);
    if (this.history.length > HISTORY_MAX) this.history = this.history.slice(-HISTORY_MAX);
    this.historyIndex = this.history.length;
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(this.history));
    } catch {
      /* quota / mode privé : on ignore */
    }
  }

  _onKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      this.submit();
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      this._historyNav(-1);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      this._historyNav(1);
    }
  }

  _historyNav(dir) {
    if (this.history.length === 0) return;
    this.historyIndex = Math.min(Math.max(this.historyIndex + dir, 0), this.history.length);
    this.input.value = this.historyIndex < this.history.length ? this.history[this.historyIndex] : "";
  }

  // --- Handoff Palette -> Console (MT-5) ---
  _onHandoff(detail) {
    if (!detail || !detail.agent) return;
    const tab = document.querySelector('.tab-btn[data-tab="console"]');
    if (tab) tab.click();
    const value = detail.task ? `@${detail.agent} ${detail.task}` : `@${detail.agent}`;
    if (this.input) {
      this.input.value = value;
      this.input.focus();
    }
    if (detail.task) this.submit();
  }

  // --- Indicateur de connexion (MT-6) ---
  _onStatus(detail) {
    if (!this.connBadge) return;
    const online = detail && (detail.ollama || detail.backend) ? true : false;
    this.connBadge.textContent = online ? "connecté" : "hors-ligne";
    this.connBadge.className = `badge ${online ? "badge-ok" : "badge-err"}`;
  }
}

export const consoleTab = new ConsoleTab();
