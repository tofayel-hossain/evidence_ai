import { appState } from '../state.js';
export class ClaimsComponent {
    constructor() {
        this.container = null;
    }
    init() {
        this.container = document.getElementById('claims-panel');
        appState.subscribe('verification', (verif) => {
            this.render(verif);
        });
    }
    render(verif) {
        if (!this.container)
            return;
        if (!verif || verif.total_claims === 0) {
            this.container.innerHTML = `
        <div class="empty-state">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
          </svg>
          <p>Ask a question to see fact checks for each statement.</p>
        </div>
      `;
            return;
        }
        const halRatePct = (verif.hallucination_rate * 100).toFixed(0);
        this.container.innerHTML = `
      <div class="claims-dashboard">
        <div class="claims-summary-bar">
          <div class="stat-pill stat-supported">
            <span class="stat-num">${verif.supported_count}</span>
            <span class="stat-lbl">Supported</span>
          </div>
          <div class="stat-pill stat-contradicted">
            <span class="stat-num">${verif.contradicted_count}</span>
            <span class="stat-lbl">Contradicted</span>
          </div>
          <div class="stat-pill stat-unverified">
            <span class="stat-num">${verif.unverified_count}</span>
            <span class="stat-lbl">Unverified</span>
          </div>
          <div class="stat-pill stat-rate">
            <span class="stat-num">${halRatePct}%</span>
            <span class="stat-lbl">Risk</span>
          </div>
        </div>

        <div class="claims-list">
          ${verif.results.map((c, i) => {
            const classLower = c.classification.toLowerCase();
            const confPct = (c.confidence * 100).toFixed(0);
            return `
              <div class="claim-item claim-${classLower}">
                <div class="claim-header">
                  <div class="claim-tag-group">
                    <span class="claim-pill pill-${classLower}">
                      ${c.classification}
                    </span>
                    ${c.numerical_conflict ? '<span class="pill-numerical">Number Mismatch</span>' : ''}
                    <span class="claim-confidence">${confPct}% match</span>
                  </div>
                  ${c.page_number ? `<span class="claim-page">Page ${c.page_number}</span>` : ''}
                </div>

                <div class="claim-text">
                  "${c.claim_text}"
                </div>

                <div class="claim-reasoning">
                  <strong>Note:</strong> ${c.reasoning}
                </div>

                <details class="premise-drawer">
                  <summary>View Source Text</summary>
                  <div class="premise-content">
                    <p class="premise-text">"${c.premise_text}"</p>
                  </div>
                </details>
              </div>
            `;
        }).join('')}
        </div>
      </div>
    `;
    }
}
//# sourceMappingURL=claims.js.map