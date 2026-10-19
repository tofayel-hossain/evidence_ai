class StateStore {
    constructor() {
        this.documents = [];
        this.selectedDocumentId = null;
        this.currentQueryResponse = null;
        this.currentVerification = null;
        this.activeTab = 'research';
        this.listeners = {
            documents: [],
            selectedDoc: [],
            queryResponse: [],
            verification: [],
            tab: []
        };
    }
    subscribe(event, fn) {
        if (!this.listeners[event])
            this.listeners[event] = [];
        this.listeners[event].push(fn);
    }
    notify(event, data) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(fn => fn(data));
        }
    }
    setDocuments(docs) {
        this.documents = docs;
        this.notify('documents', docs);
    }
    getDocuments() {
        return this.documents;
    }
    setSelectedDocumentId(id) {
        this.selectedDocumentId = id;
        this.notify('selectedDoc', id);
    }
    getSelectedDocumentId() {
        return this.selectedDocumentId;
    }
    setQueryResponse(resp) {
        this.currentQueryResponse = resp;
        this.notify('queryResponse', resp);
    }
    getQueryResponse() {
        return this.currentQueryResponse;
    }
    setVerification(verif) {
        this.currentVerification = verif;
        this.notify('verification', verif);
    }
    getVerification() {
        return this.currentVerification;
    }
    setActiveTab(tab) {
        this.activeTab = tab;
        this.notify('tab', tab);
    }
    getActiveTab() {
        return this.activeTab;
    }
}
export const appState = new StateStore();
//# sourceMappingURL=state.js.map