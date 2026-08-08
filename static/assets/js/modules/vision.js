// VisionUploader — Responsabilité unique : câbler la zone d'upload vision
// (clic → sélecteur de fichier, change → analyse, drop → analyse,
// paste/Ctrl+V → analyse du presse-papiers).
// DIP : aucun élément DOM global, tout est injecté ; la logique d'analyse
// (POST /api/vision) reste à l'appelant via le callback onAnalyze(dataUrl, file).

// Extrait la première image du presse-papiers d'un événement paste, ou null.
function readClipboardImage(e) {
  const items = e.clipboardData?.items;
  if (!items) return null;
  for (const item of items) {
    if (item.type?.startsWith('image/')) return item.getAsFile();
  }
  return null;
}

class VisionUploader {
  attachZone(zone, fileInput, onAnalyze) {
    this._fileInput = fileInput;
    this._onAnalyze = onAnalyze;

    zone.addEventListener('click', () => this._fileInput.click());
    this._fileInput.addEventListener('change', () => this._handleFile());

    zone.addEventListener('dragover', (e) => {
      e.preventDefault();
      zone.classList.add('dragover');
    });
    zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
    zone.addEventListener('drop', (e) => {
      e.preventDefault();
      zone.classList.remove('dragover');
      const file = e.dataTransfer?.files?.[0];
      if (file) this._send(file);
    });
    zone.addEventListener('paste', (e) => {
      const file = readClipboardImage(e);
      if (file) {
        e.preventDefault();
        this._send(file);
      }
    });
  }

  readFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(new Error('Lecture du fichier impossible'));
      reader.readAsDataURL(file);
    });
  }

  _handleFile() {
    const file = this._fileInput.files?.[0];
    if (file) this._send(file);
  }

  async _send(file) {
    try {
      const dataUrl = await this.readFile(file);
      this._onAnalyze(dataUrl, file);
    } catch (err) {
      this._onAnalyze(null, file, err);
    }
  }
}

export { VisionUploader };