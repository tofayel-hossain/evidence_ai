import { DocumentDTO, QueryResponseDTO, VerificationResponseDTO } from './types.js';

type Listener<T> = (data: T) => void;

class StateStore {
  private documents: DocumentDTO[] = [];
  private selectedDocumentId: string | null = null;
  private currentQueryResponse: QueryResponseDTO | null = null;
  private currentVerification: VerificationResponseDTO | null = null;
  private activeTab: 'research' | 'documents' = 'research';

  private listeners: Record<string, Listener<any>[]> = {
    documents: [],
    selectedDoc: [],
    queryResponse: [],
    verification: [],
    tab: []
  };

  public subscribe<T>(event: string, fn: Listener<T>) {
    if (!this.listeners[event]) this.listeners[event] = [];
    this.listeners[event].push(fn);
  }

  private notify(event: string, data: any) {
    if (this.listeners[event]) {
      this.listeners[event].forEach(fn => fn(data));
    }
  }

  public setDocuments(docs: DocumentDTO[]) {
    this.documents = docs;
    this.notify('documents', docs);
  }

  public getDocuments(): DocumentDTO[] {
    return this.documents;
  }

  public setSelectedDocumentId(id: string | null) {
    this.selectedDocumentId = id;
    this.notify('selectedDoc', id);
  }

  public getSelectedDocumentId(): string | null {
    return this.selectedDocumentId;
  }

  public setQueryResponse(resp: QueryResponseDTO | null) {
    this.currentQueryResponse = resp;
    this.notify('queryResponse', resp);
  }

  public getQueryResponse(): QueryResponseDTO | null {
    return this.currentQueryResponse;
  }

  public setVerification(verif: VerificationResponseDTO | null) {
    this.currentVerification = verif;
    this.notify('verification', verif);
  }

  public getVerification(): VerificationResponseDTO | null {
    return this.currentVerification;
  }

  public setActiveTab(tab: 'research' | 'documents') {
    this.activeTab = tab;
    this.notify('tab', tab);
  }

  public getActiveTab(): string {
    return this.activeTab;
  }
}

export const appState = new StateStore();
