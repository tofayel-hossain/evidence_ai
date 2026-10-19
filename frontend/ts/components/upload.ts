import { ApiClient } from '../api.js';
import { appState } from '../state.js';

export class UploadComponent {
  private dropZone: HTMLElement | null = null;
  private fileInput: HTMLInputElement | null = null;
  private progressContainer: HTMLElement | null = null;
  private progressBar: HTMLElement | null = null;
  private progressText: HTMLElement | null = null;
  private statusMessage: HTMLElement | null = null;

  public init() {
    this.dropZone = document.getElementById('drop-zone');
    this.fileInput = document.getElementById('file-input') as HTMLInputElement;
    this.progressContainer = document.getElementById('upload-progress-container');
    this.progressBar = document.getElementById('upload-progress-bar');
    this.progressText = document.getElementById('upload-progress-text');
    this.statusMessage = document.getElementById('upload-status-message');

    if (!this.dropZone || !this.fileInput) return;

    this.dropZone.addEventListener('click', () => this.fileInput?.click());
    this.fileInput.addEventListener('click', (e) => e.stopPropagation());

    this.fileInput.addEventListener('change', (e) => {
      const files = (e.target as HTMLInputElement).files;
      if (files && files.length > 0) {
        this.handleUpload(files[0]);
      }
    });

    // Drag and drop events
    ['dragenter', 'dragover'].forEach(name => {
      this.dropZone?.addEventListener(name, (e) => {
        e.preventDefault();
        this.dropZone?.classList.add('drag-active');
      });
    });

    ['dragleave', 'drop'].forEach(name => {
      this.dropZone?.addEventListener(name, (e) => {
        e.preventDefault();
        this.dropZone?.classList.remove('drag-active');
      });
    });

    this.dropZone.addEventListener('drop', (e: DragEvent) => {
      const files = e.dataTransfer?.files;
      if (files && files.length > 0) {
        this.handleUpload(files[0]);
      }
    });
  }

  private async handleUpload(file: File) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      this.showStatus('Only PDF files are supported.', 'error');
      return;
    }

    if (file.size === 0) {
      this.showStatus('The selected file is empty (0 bytes).', 'error');
      return;
    }

    if (file.size > 25 * 1024 * 1024) {
      this.showStatus('File size exceeds the 25MB limit.', 'error');
      return;
    }

    this.showProgress(0);
    this.showStatus(`Extracting and indexing "${file.name}"...`, 'info');

    try {
      const doc = await ApiClient.uploadDocument(file, (pct) => {
        this.showProgress(pct);
      });

      this.showStatus(
        doc.status === 'scanned_warning'
          ? `Document uploaded, but has scanned image content without extractable text.`
          : `Successfully processed "${doc.filename}" (${doc.page_count} pages indexed).`,
        doc.status === 'scanned_warning' ? 'warning' : 'success'
      );

      // Refresh documents
      const docs = await ApiClient.getDocuments();
      appState.setDocuments(docs);
      appState.setSelectedDocumentId(doc.id);
    } catch (err: any) {
      this.showStatus(`Upload failed: ${err.message}`, 'error');
    } finally {
      setTimeout(() => this.hideProgress(), 3000);
      if (this.fileInput) this.fileInput.value = '';
    }
  }

  private showProgress(pct: number) {
    if (this.progressContainer) this.progressContainer.style.display = 'block';
    if (this.progressBar) this.progressBar.style.width = `${pct}%`;
    if (this.progressText) this.progressText.textContent = `${pct}%`;
  }

  private hideProgress() {
    if (this.progressContainer) this.progressContainer.style.display = 'none';
  }

  private showStatus(msg: string, type: 'info' | 'success' | 'warning' | 'error') {
    if (!this.statusMessage) return;
    this.statusMessage.textContent = msg;
    this.statusMessage.className = `status-banner status-${type}`;
    this.statusMessage.style.display = 'block';
  }
}
