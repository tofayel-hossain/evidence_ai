import { ApiClient } from '../api.js';
import { appState } from '../state.js';
import { DocumentDTO } from '../types.js';

export class LibraryComponent {
  private container: HTMLElement | null = null;
  private searchInput: HTMLInputElement | null = null;
  private documentCount: HTMLElement | null = null;

  public init() {
    this.container = document.getElementById('document-list');
    this.searchInput = document.getElementById('doc-search') as HTMLInputElement;
    this.documentCount = document.getElementById('doc-count-badge');

    appState.subscribe<DocumentDTO[]>('documents', (docs) => this.render(docs));
    appState.subscribe<string | null>('selectedDoc', () => this.render(appState.getDocuments()));

    this.searchInput?.addEventListener('input', () => {
      this.render(appState.getDocuments());
    });
  }

  private render(docs: DocumentDTO[]) {
    if (!this.container) return;
    const filter = this.searchInput?.value.toLowerCase().trim() || '';
    const filtered = docs.filter(d =>
      d.filename.toLowerCase().includes(filter) ||
      (d.title && d.title.toLowerCase().includes(filter)) ||
      (d.author && d.author.toLowerCase().includes(filter))
    );

    if (this.documentCount) {
      this.documentCount.textContent = `${docs.length}`;
    }

    if (filtered.length === 0) {
      this.container.innerHTML = `
        <div class="empty-state">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
          </svg>
          <p>${filter ? 'No papers found.' : 'No papers uploaded yet.'}</p>
        </div>
      `;
      return;
    }

    const selectedId = appState.getSelectedDocumentId();

    this.container.innerHTML = filtered.map(doc => {
      const isSelected = doc.id === selectedId;
      const sizeMb = (doc.file_size_bytes / (1024 * 1024)).toFixed(1);
      const isScanned = doc.status === 'scanned_warning';

      return `
        <div class="doc-card ${isSelected ? 'selected' : ''}" data-id="${doc.id}">
          <div class="doc-card-header">
            <h4 class="doc-title" title="${doc.title || doc.filename}">${doc.title || doc.filename}</h4>
            <button class="delete-btn" data-id="${doc.id}" title="Delete paper">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
            </button>
          </div>
          ${doc.author && doc.author !== 'Unknown' ? `<p class="doc-author">${doc.author}</p>` : ''}
          <div class="doc-card-footer">
            <span class="badge ${isScanned ? 'badge-warning' : 'badge-indexed'}">
              ${isScanned ? 'Scanned' : 'Ready'}
            </span>
            <span class="doc-meta">${doc.page_count} pages • ${sizeMb} MB</span>
          </div>
        </div>
      `;
    }).join('');

    // Attach click listeners
    this.container.querySelectorAll('.doc-card').forEach(card => {
      card.addEventListener('click', (e) => {
        if ((e.target as HTMLElement).closest('.delete-btn')) return;
        const id = card.getAttribute('data-id');
        if (id) {
          appState.setSelectedDocumentId(id === selectedId ? null : id);
        }
      });
    });

    this.container.querySelectorAll('.delete-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const id = btn.getAttribute('data-id');
        if (!id) return;
        if (confirm('Delete this paper?')) {
          try {
            await ApiClient.deleteDocument(id);
            const remaining = await ApiClient.getDocuments();
            appState.setDocuments(remaining);
            if (appState.getSelectedDocumentId() === id) {
              appState.setSelectedDocumentId(null);
            }
          } catch (err: any) {
            alert(`Delete failed: ${err.message}`);
          }
        }
      });
    });
  }
}
