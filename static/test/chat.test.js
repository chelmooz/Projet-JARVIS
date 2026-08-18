import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ChatImage, buildFeedbackRow, renderAssistantMsg } from '../assets/js/modules/chat.js';

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

describe('Feedback buttons', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="chat-messages"></div>';
  });

  it('buildFeedbackRow creates two feedback buttons (up and down) and a copy button', () => {
    const msg = { id: 'msg-123', content: 'Test response' };
    const row = buildFeedbackRow('conv-456', msg);

    expect(row.className).toBe('feedback-row');
    const buttons = row.querySelectorAll('.fb-btn');
    expect(buttons.length).toBe(3);

    const upBtn = row.querySelector('[data-act="up"]');
    const downBtn = row.querySelector('[data-act="down"]');
    const copyBtn = row.querySelector('[data-act="copy"]');

    expect(upBtn).not.toBeNull();
    expect(downBtn).not.toBeNull();
    expect(copyBtn).not.toBeNull();

    expect(upBtn.textContent).toBe('👍');
    expect(downBtn.textContent).toBe('👎');
    expect(copyBtn.textContent).toBe('📋');
  });

  it('renderAssistantMsg includes feedback row when msg.id and convId provided', () => {
    const msg = {
      id: 'msg-123',
      content: 'Test response',
      agent: '@cyber',
      model: 'test-model',
      backend: 'ollama'
    };
    const div = renderAssistantMsg('conv-456', msg);

    expect(div.className).toBe('msg assistant');
    const feedbackRow = div.querySelector('.feedback-row');
    expect(feedbackRow).not.toBeNull();

    const buttons = feedbackRow.querySelectorAll('.fb-btn');
    expect(buttons.length).toBe(3);
  });

  it('renderAssistantMsg does NOT include feedback row when msg.id is missing', () => {
    const msg = {
      content: 'Test response',
      agent: '@cyber',
      model: 'test-model',
      backend: 'ollama'
    };
    const div = renderAssistantMsg('conv-456', msg);

    const feedbackRow = div.querySelector('.feedback-row');
    expect(feedbackRow).toBeNull();
  });

  it('feedback buttons have visible styles (not display:none)', () => {
    const msg = { id: 'msg-123', content: 'Test response' };
    const row = buildFeedbackRow('conv-456', msg);

    const buttons = row.querySelectorAll('.fb-btn');
    buttons.forEach(btn => {
      expect(btn.style.display).not.toBe('none');
      expect(btn.style.visibility).not.toBe('hidden');
      expect(btn.style.opacity).not.toBe('0');
    });
  });
});