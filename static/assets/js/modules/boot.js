// boot.js — Composition root du frontend : câble les modules au DOM.
// Responsabilité unique : wiring. Aucune logique métier ici (testée dans
// les modules unitaires) ; le legacy app.js (script classique) est laissé
// intact et cohabite par des points d'accroche explicites (window).

import { VisionUploader } from './vision.js';
import { ChatImage } from './chat.js';
import { palette } from './command-palette.js';
import { consoleTab } from './console-tab.js';

function bootstrapVision(zoneId, fileId, onAnalyze) {
  const zone = document.getElementById(zoneId);
  const fileInput = document.getElementById(fileId);
  if (!zone || !fileInput) return;
  const uploader = new VisionUploader();
  uploader.attachZone(zone, fileInput, onAnalyze);
  return uploader;
}

function bootstrapChat() {
  const chat = new ChatImage();
  chat.init();
  window.__jarvisImage = chat;
}

bootstrapChat();

// Zone d'upload de l'onglet Vision : l'analyse (preview + POST /api/vision)
// reste déléguée à app.js via le global historique window.handleVisionDataUrl
// (défini par app.js après chargement) — le module ne sait pas POSTer.
bootstrapVision('upload-zone', 'vision-file', (dataUrl, file, err) => {
  const handler = window.handleVisionDataUrl;
  if (handler) handler(dataUrl, file, err);
});

// --- Console Tab + Command Palette (Ctrl+K) ---
// Listener unique Ctrl+K / Cmd+K monté une fois, actif sur tout le document.
consoleTab.mount();
palette.mount();

document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
    e.preventDefault();
    palette.toggle();
  }
});

window.__jarvisPalette = palette;
window.__jarvisConsole = consoleTab;