import { ApiClient } from './api.js';
import { appState } from './state.js';
import { UploadComponent } from './components/upload.js';
import { LibraryComponent } from './components/library.js';
import { ChatComponent } from './components/chat.js';
import { ClaimsComponent } from './components/claims.js';

document.addEventListener('DOMContentLoaded', async () => {
  // Initialize UI Components
  const uploadComp = new UploadComponent();
  uploadComp.init();

  const libraryComp = new LibraryComponent();
  libraryComp.init();

  const chatComp = new ChatComponent();
  chatComp.init();

  const claimsComp = new ClaimsComponent();
  claimsComp.init();

  // Tab Navigation
  const navTabs = document.querySelectorAll('.nav-tab');
  navTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.getAttribute('data-tab');
      if (!target) return;

      navTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');

      document.querySelectorAll('.tab-view').forEach(view => {
        view.classList.remove('active');
      });

      const activeView = document.getElementById(`view-${target}`);
      if (activeView) activeView.classList.add('active');
    });
  });

  // Initial Data Load
  try {
    const docs = await ApiClient.getDocuments();
    appState.setDocuments(docs);
    if (docs.length > 0) {
      appState.setSelectedDocumentId(docs[0].id);
    }
  } catch (err) {
    console.warn('Initial document fetch error:', err);
  }
});
