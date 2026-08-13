// command-palette.js — Palette globale Ctrl+K : overlay + autocomplétion @agent.
// DOM limité à l'overlay (injecté au mount). Délègue l'envoi à console-client.js.

import { escHtml } from "./utils.js";
import { fetchAgents, sendCommand, consoleStore, parseCommand } from "./console-client.js";

const PALETTE_HTML = `
  <div id="command-palette" class="palette-overlay" hidden>
    <div class="palette-box" role="dialog" aria-label="Palette de commandes">
      <input id="palette-input" class="palette-input" type="text"
             placeholder="Commande JARVIS… ex: @cyber scan le firewall" autocomplete="off" />
      <ul id="palette-suggestions" class="palette-suggestions"></ul>
      <div id="palette-result" class="palette-result" hidden></div>
      <div class="palette-actions">
        <button id="palette-open-console" class="btn btn-secondary" type="button">Ouvrir en Console</button>
        <span class="palette-hint">Ctrl/⌘+K pour ouvrir · Échap pour fermer</span>
      </div>
    </div>
  </div>
`;

export class CommandPalette {
  constructor() {
    this.agents = [];
    this.overlay = null;
    this.input = null;
    this.suggestions = null;
    this.result = null;
    this._lastAgent = null;
    this._lastTask = null;
  }

  async mount() {
    if (this.overlay) return this;
    const host = document.createElement("div");
    host.innerHTML = PALETTE_HTML.trim();
    this.overlay = host.firstElementChild;
    document.body.appendChild(this.overlay);

    this.input = document.getElementById("palette-input");
    this.suggestions = document.getElementById("palette-suggestions");
    this.result = document.getElementById("palette-result");

    this.input.addEventListener("input", () => this._onInput());
    this.input.addEventListener("keydown", (e) => this._onInputKey(e));
    document.getElementById("palette-open-console").addEventListener("click", () => this.handoff());

    // Suggestions cliquables (délégation)
    this.suggestions.addEventListener("click", (e) => {
      const li = e.target.closest("[data-agent]");
      if (!li) return;
      this.input.value = `@${li.dataset.agent} `;
      this.input.focus();
      this._renderSuggestions("");
    });

    try {
      this.agents = await fetchAgents();
    } catch {
      this.agents = [];
    }
    return this;
  }

  isOpen() {
    return !!this.overlay && !this.overlay.hasAttribute("hidden");
  }

  open() {
    if (!this.overlay) return;
    this.overlay.removeAttribute("hidden");
    this.input.value = "";
    this._clearResult();
    this._renderSuggestions("");
    this.input.focus();
  }

  close() {
    if (!this.overlay) return;
    this.overlay.setAttribute("hidden", "");
    this.input.value = "";
    this._clearResult();
    this._renderSuggestions("");
    if (document.activeElement === this.input) this.input.blur();
  }

  toggle() {
    this.isOpen() ? this.close() : this.open();
  }

  // --- Autocomplétion (filtre sur les préfixes d'agents) ---
  _onInput() {
    this._renderSuggestions(this.input.value);
  }

  _renderSuggestions(query) {
    const q = query.trim().toLowerCase();
    const matches = this.agents.filter((a) => !q || `@${a.key}`.startsWith(q) || a.name.toLowerCase().includes(q));
    if (!q || matches.length === 0) {
      this.suggestions.innerHTML = "";
      return;
    }
    this.suggestions.innerHTML = matches
      .map(
        (a) =>
          `<li class="palette-suggestion" data-agent="${escHtml(a.key)}">` +
          `<span class="badge badge-agent">@${escHtml(a.key)}</span>` +
          `<span class="palette-suggestion-name">${escHtml(a.name)}</span>` +
          (a.model ? `<span class="palette-suggestion-model">${escHtml(a.model)}</span>` : "") +
          `</li>`,
      )
      .join("");
  }

  // --- Soumission (Entrée) ---
  async _onInputKey(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      this.close();
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      await this.submit();
    }
  }

  async submit() {
    const value = this.input.value.trim();
    if (!value) return;

    let parsed;
    try {
      parsed = parseCommand(value);
    } catch (err) {
      this._clearResult();
      this.result.removeAttribute("hidden");
      this.result.innerHTML = `<div class="palette-error">${escHtml(err.message)}</div>`;
      return;
    }

    this._clearResult();
    this.result.removeAttribute("hidden");
    this.result.innerHTML = `<span class="palette-spinner">…</span>`;

    const res = await sendCommand(parsed, { source: "palette" });

    if (res.ok) {
      const text = res.data && res.data.response ? res.data.response : JSON.stringify(res.data);
      this.result.innerHTML = `<div class="palette-answer">${escHtml(text)}</div>`;
    } else {
      this.result.innerHTML = `<div class="palette-error">${escHtml(res.error)}</div>`;
    }
  }

  // --- Handoff Palette -> Console (MT-5) ---
  handoff() {
    const value = this.input.value.trim();
    let agent = "";
    let task = "";
    try {
      const parsed = parseCommand(value);
      agent = parsed.agent;
      task = parsed.task;
    } catch {
      const m = value.match(/^@(\w+)/);
      if (m) agent = m[1];
    }
    if (agent) {
      consoleStore.setLast({ agent, task, source: "palette" });
    }
    document.dispatchEvent(new CustomEvent("jarvis:palette-handoff", { detail: { agent, task } }));
    this.close();
  }

  _clearResult() {
    if (this.result) {
      this.result.setAttribute("hidden", "");
      this.result.innerHTML = "";
    }
  }
}

export const palette = new CommandPalette();
