import { ApiClient } from '../api.js';
import { appState } from '../state.js';
import { QueryResponseDTO } from '../types.js';

export class ChatComponent {
  private form: HTMLFormElement | null = null;
  private input: HTMLInputElement | null = null;
  private submitBtn: HTMLButtonElement | null = null;
  private methodSelect: HTMLSelectElement | null = null;
  private answerContainer: HTMLElement | null = null;
  private activeDocIndicator: HTMLElement | null = null;

  public init() {
    this.form = document.getElementById('query-form') as HTMLFormElement;
    this.input = document.getElementById('query-input') as HTMLInputElement;
    this.submitBtn = document.getElementById('query-submit') as HTMLButtonElement;
    this.methodSelect = document.getElementById('retrieval-method') as HTMLSelectElement;
    this.answerContainer = document.getElementById('answer-panel');
    this.activeDocIndicator = document.getElementById('active-doc-badge');

    this.form?.addEventListener('submit', (e) => {
      e.preventDefault();
      this.handleSubmit();
    });

    appState.subscribe<string | null>('selectedDoc', (docId) => {
      this.updateActiveDocIndicator(docId);
    });

    appState.subscribe<QueryResponseDTO | null>('queryResponse', (resp) => {
      this.renderAnswer(resp);
    });
  }

  private updateActiveDocIndicator(docId: string | null) {
    if (!this.activeDocIndicator) return;
    if (docId) {
      const doc = appState.getDocuments().find(d => d.id === docId);
      this.activeDocIndicator.textContent = doc ? (doc.title || doc.filename) : docId;
      this.activeDocIndicator.style.display = 'inline-block';
    } else {
      this.activeDocIndicator.textContent = 'All Papers';
      this.activeDocIndicator.style.display = 'inline-block';
    }
  }

  private async handleSubmit() {
    const question = this.input?.value.trim();
    if (!question) return;

    const method = this.methodSelect?.value || 'auto';
    const docId = appState.getSelectedDocumentId() || undefined;

    this.setLoading(true);
    appState.setVerification(null);

    try {
      const resp = await ApiClient.askQuestion(question, docId, method, 5);
      appState.setQueryResponse(resp);
      this.setLoading(false);

      // Auto-trigger claim verification in the background without blocking the answer display
      ApiClient.verifyClaims(resp.answer, docId)
        .then(verif => {
          appState.setVerification(verif);
        })
        .catch(err => {
          console.warn('Auto verification error:', err);
        });
    } catch (err: any) {
      if (this.answerContainer) {
        this.answerContainer.innerHTML = `
          <div class="status-banner status-error">
            <strong>Error:</strong> ${err.message}
          </div>
        `;
      }
    } finally {
      this.setLoading(false);
    }
  }

  private setLoading(isLoading: boolean) {
    if (this.submitBtn) {
      this.submitBtn.disabled = isLoading;
      this.submitBtn.innerHTML = isLoading
        ? `<span class="spinner"></span> Searching...`
        : `Ask`;
    }
  }

  private renderAnswer(resp: QueryResponseDTO | null) {
    if (!this.answerContainer || !resp) return;

    // Update auto-adaptive strategy indicator
    const activeStrategyElem = document.getElementById('active-strategy-name');
    if (activeStrategyElem && resp.retrieval_method_used) {
      activeStrategyElem.textContent = resp.retrieval_method_used;
    }

    // Highlight citation tags [Page X] as interactive clickable badges
    let formattedAnswer = resp.answer.replace(
      /\[(?:([a-zA-Z0-9_\-]+),\s*)?[Pp]ages?\s*([0-9]+(?:\s*[-–,]\s*[0-9]+)*)\]/g,
      (match, doc, page) => {
        return `<span class="citation-pill" data-page="${page}" title="Click to inspect source evidence">${match}</span>`;
      }
    );

    const hasSufficient = resp.has_sufficient_evidence;

    this.answerContainer.innerHTML = `
      <div class="answer-card">
        <div class="answer-header">
          <div class="answer-meta">
            <span class="badge ${hasSufficient ? 'badge-indexed' : 'badge-warning'}">
              ${hasSufficient ? 'From Paper' : 'No Evidence'}
            </span>
            <span class="meta-item">Search: <strong>${resp.retrieval_method_used}</strong></span>
            <span class="meta-item">Time: <strong>${resp.latency_ms}ms</strong></span>
            <span class="meta-item">Sources: <strong>${resp.citations.length}</strong></span>
          </div>
          <button id="trigger-verify-btn" class="secondary-btn">
            Check Facts
          </button>
        </div>

        <div class="question-display">
          <strong>Q:</strong> ${resp.question}
        </div>

        <div class="answer-body">
          ${formattedAnswer}
        </div>

        ${resp.citations.length > 0 ? `
          <div class="citations-section">
            <h5>Sources (${resp.citations.length})</h5>
            <div class="citations-grid">
              ${resp.citations.map(c => `
                <div class="citation-card ${c.is_valid ? 'valid' : 'invalid'}" data-page="${c.page_number}">
                  <div class="cite-top">
                    <span class="cite-page">Page ${c.page_number}</span>
                    <span class="cite-status ${c.is_valid ? 'text-success' : 'text-danger'}">
                      ${c.is_valid ? '✓ Verified' : '✗ Check'}
                    </span>
                  </div>
                  <p class="cite-snippet">"${c.cited_snippet}"</p>
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}
      </div>
    `;

    // Attach listeners to citation pills
    this.answerContainer.querySelectorAll('.citation-pill, .citation-card').forEach(el => {
      el.addEventListener('click', () => {
        const page = el.getAttribute('data-page');
        if (page) {
          const evt = new CustomEvent('inspectEvidence', { detail: { page: parseInt(page) } });
          window.dispatchEvent(evt);
        }
      });
    });

    document.getElementById('trigger-verify-btn')?.addEventListener('click', async () => {
      const docId = appState.getSelectedDocumentId() || undefined;
      const btn = document.getElementById('trigger-verify-btn') as HTMLButtonElement;
      if (btn) btn.disabled = true;
      try {
        const verif = await ApiClient.verifyClaims(resp.answer, docId);
        appState.setVerification(verif);
      } catch (err: any) {
        alert(`Verification failed: ${err.message}`);
      } finally {
        if (btn) btn.disabled = false;
      }
    });
  }
}
