import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ChatImage } from '../assets/js/modules/chat.js';

function imageFile() {
  return new File(['fake-png-bytes'], 'clipboard.png', { type: 'image/png' });
}

function makePasteEvent(file) {
  const ev = new Event('paste', { bubbles: true, cancelable: true });
  Object.defineProperty(ev, 'clipboardData', {
    value: { items: [{ type: file ? file.type : 'text/plain', getAsFile: () => file }] },
  });
  return ev;
}

describe('ChatImage', () => {
  let chat;

  beforeEach(() => {
    document.body.innerHTML = `
      <textarea id="chat-input"></textarea>
      <div id="chat-image-badge" class="d-none"></div>
      <button id="chat-image-clear"></button>
    `;
    chat = new ChatImage();
    chat.init();
  });

  it('paste global avec image → pendingImage set + badge visible', async () => {
    const input = document.getElementById('chat-input');
    document.body.dispatchEvent(makePasteEvent(imageFile()));

    await vi.waitFor(() => expect(chat.pendingImage()).toMatch(/^data:image\/png;base64,/));
    const badge = document.getElementById('chat-image-badge');
    expect(badge.classList.contains('d-none')).toBe(false);
  });

  it('paste dans le textarea avec du texte seul → aucun changement (texte libre intact)', () => {
    const input = document.getElementById('chat-input');
    input.dispatchEvent(makePasteEvent(null));

    expect(chat.pendingImage()).toBeNull();
    const badge = document.getElementById('chat-image-badge');
    expect(badge.classList.contains('d-none')).toBe(true);
  });

  it('bouton effacer → pendingImage null + badge caché', async () => {
    document.body.dispatchEvent(makePasteEvent(imageFile()));
    await vi.waitFor(() => expect(chat.pendingImage()).toMatch(/^data:/));

    document.getElementById('chat-image-clear').click();

    expect(chat.pendingImage()).toBeNull();
    expect(document.getElementById('chat-image-badge').classList.contains('d-none')).toBe(true);
  });
});