// ChatImage — Responsabilité unique : image jointe au message du chat
// (collage Ctrl+V global + badge visuel + effacement).
// DIP : les éléments DOM sont situés par id (convention), la lecture du
// presse-papiers est déléguée au helper partagé.

const BADGE_ID = 'chat-image-badge';
const CLEAR_ID = 'chat-image-clear';
const CHAT_INPUT_ID = 'chat-input';

function readClipboardImage(e) {
  const items = e.clipboardData?.items;
  if (!items) return null;
  for (const item of items) {
    if (item.type?.startsWith('image/')) return item.getAsFile();
  }
  return null;
}

class ChatImage {
  constructor() {
    this._dataUrl = null;
    this._badgeEl = null;
    this._clearEl = null;
  }

  init() {
    this._badgeEl = document.getElementById(BADGE_ID);
    this._clearEl = document.getElementById(CLEAR_ID);
    if (this._clearEl) {
      this._clearEl.addEventListener('click', () => this.clear());
    }
    document.addEventListener('paste', (e) => this._handlePaste(e), true);
  }

  pendingImage() {
    return this._dataUrl;
  }

  setImage(dataUrl) {
    this._dataUrl = dataUrl || null;
    this._render();
  }

  clear() {
    this._dataUrl = null;
    this._render();
  }

  _handlePaste(e) {
    const file = readClipboardImage(e);
    if (!file || e.target?.id === CHAT_INPUT_ID) return;
    e.preventDefault();
    const reader = new FileReader();
    reader.onload = () => this.setImage(reader.result);
    reader.readAsDataURL(file);
  }

  _render() {
    if (this._badgeEl) {
      this._badgeEl.classList.toggle('d-none', !this._dataUrl);
      if (this._dataUrl) {
        this._badgeEl.title = 'Image jointe — Ctrl+V pour la remplacer, ✕ pour la retirer';
      }
    }
  }
}

export { ChatImage };