import { describe, it, expect, beforeEach, vi } from 'vitest';
import { VisionUploader } from '../assets/js/modules/vision.js';

function imageFile() {
  return new File(['fake-png-bytes'], 'shot.png', { type: 'image/png' });
}

describe('VisionUploader', () => {
  let uploader;

  beforeEach(() => {
    uploader = new VisionUploader();
  });

  it('déclenche le sélecteur de fichier au clic sur la zone', () => {
    const zone = document.createElement('div');
    const input = document.createElement('input');
    input.type = 'file';
    input.click = () => { input._clicked = true; };
    zone.appendChild(input);
    uploader.attachZone(zone, input, () => {});

    zone.dispatchEvent(new MouseEvent('click'));

    expect(input._clicked).toBe(true);
  });

  it('upload au changement de fichier (input change) — bug réel clé USB : le clic ouvrait le dialogue mais le fichier choisi n’était jamais analysé', async () => {
    const input = document.createElement('input');
    input.type = 'file';
    const onAnalyze = vi.fn();
    uploader.attachZone(document.createElement('div'), input, onAnalyze);

    Object.defineProperty(input, 'files', { value: [imageFile()], configurable: true });
    input.dispatchEvent(new Event('change'));

    await vi.waitFor(() => expect(onAnalyze).toHaveBeenCalledTimes(1));
    const [dataUrl, file] = onAnalyze.mock.calls[0];
    expect(dataUrl).toMatch(/^data:image\/png;base64,/);
    expect(file.name).toBe('shot.png');
  });

  it('upload au drop d’un fichier (comportement existant préservé)', async () => {
    const uiZone = document.createElement('div');
    const input = document.createElement('input');
    input.type = 'file';
    const onAnalyze = vi.fn();
    uploader.attachZone(uiZone, input, onAnalyze);

    const dropEvent = new Event('drop');
    Object.defineProperty(dropEvent, 'dataTransfer', {
      value: { files: [imageFile()] },
    });
    Object.defineProperty(input, 'files', { value: [imageFile()], configurable: true });
    uiZone.dispatchEvent(dropEvent);

    await vi.waitFor(() => expect(onAnalyze).toHaveBeenCalledTimes(1));
  });

  it('coller une image (Ctrl+V) sur la zone déclenche l’analyse', async () => {
    const uiZone = document.createElement('div');
    const input = document.createElement('input');
    input.type = 'file';
    const onAnalyze = vi.fn();
    uploader.attachZone(uiZone, input, onAnalyze);

    const pasteEvent = new Event('paste');
    Object.defineProperty(pasteEvent, 'clipboardData', {
      value: { items: [{ type: 'image/png', getAsFile: () => imageFile() }] },
    });
    uiZone.dispatchEvent(pasteEvent);

    await vi.waitFor(() => expect(onAnalyze).toHaveBeenCalledTimes(1));
    const [dataUrl, file] = onAnalyze.mock.calls[0];
    expect(dataUrl).toMatch(/^data:image\/png;base64,/);
    expect(file.name).toBe('shot.png');
  });

  it('ignorer un collage sans image', async () => {
    const uiZone = document.createElement('div');
    const input = document.createElement('input');
    input.type = 'file';
    const onAnalyze = vi.fn();
    uploader.attachZone(uiZone, input, onAnalyze);

    const textPaste = new Event('paste');
    Object.defineProperty(textPaste, 'clipboardData', {
      value: { items: [{ type: 'text/plain', getAsFile: () => null }] },
    });
    uiZone.dispatchEvent(textPaste);

    expect(onAnalyze).not.toHaveBeenCalled();
  });
});