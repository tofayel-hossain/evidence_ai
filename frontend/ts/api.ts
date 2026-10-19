import {
  DocumentDTO,
  DocumentChunkDTO,
  QueryResponseDTO,
  VerificationResponseDTO,
  ConversationDTO
} from './types.js';

const API_BASE = (() => {
  if (typeof window !== 'undefined' && window.location) {
    if (window.location.port === '8000') {
      return '/api/v1';
    }
    if (window.location.protocol === 'file:' || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
      return 'http://localhost:8000/api/v1';
    }
  }
  return '/api/v1';
})();

export class ApiClient {
  private static token: string | null = null;

  public static setToken(token: string) {
    this.token = token;
    localStorage.setItem('evidenceai_token', token);
  }

  public static getToken(): string | null {
    if (!this.token) {
      this.token = localStorage.getItem('evidenceai_token');
    }
    return this.token;
  }

  private static getHeaders(isJson: boolean = true): HeadersInit {
    const headers: Record<string, string> = {};
    if (isJson) {
      headers['Content-Type'] = 'application/json';
    }
    const tok = this.getToken();
    if (tok) {
      headers['Authorization'] = `Bearer ${tok}`;
    }
    return headers;
  }

  public static async getDocuments(): Promise<DocumentDTO[]> {
    const res = await fetch(`${API_BASE}/documents`, {
      headers: this.getHeaders()
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  public static async uploadDocument(
    file: File,
    onProgress?: (pct: number) => void
  ): Promise<DocumentDTO> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE}/documents/upload`);

      const tok = this.getToken();
      if (tok) {
        xhr.setRequestHeader('Authorization', `Bearer ${tok}`);
      }

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) {
          const pct = Math.round((e.loaded / e.total) * 100);
          onProgress(pct);
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
        } else {
          try {
            const err = JSON.parse(xhr.responseText);
            reject(new Error(err.detail || 'Upload failed'));
          } catch {
            reject(new Error(xhr.statusText || 'Upload failed'));
          }
        }
      };

      xhr.onerror = () => reject(new Error('Network error: Unable to reach backend server. Please verify the backend is running at http://localhost:8000.'));

      const formData = new FormData();
      formData.append('file', file);
      xhr.send(formData);
    });
  }

  public static async deleteDocument(id: string): Promise<void> {
    const res = await fetch(`${API_BASE}/documents/${id}`, {
      method: 'DELETE',
      headers: this.getHeaders()
    });
    if (!res.ok) throw new Error(await res.text());
  }

  public static async getDocumentChunks(id: string, page?: number): Promise<DocumentChunkDTO[]> {
    const url = page ? `${API_BASE}/documents/${id}/chunks?page_number=${page}` : `${API_BASE}/documents/${id}/chunks`;
    const res = await fetch(url, { headers: this.getHeaders() });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  public static async askQuestion(
    question: string,
    documentId?: string,
    method: string = 'hybrid',
    topK: number = 5
  ): Promise<QueryResponseDTO> {
    const res = await fetch(`${API_BASE}/query`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({
        question,
        document_id: documentId || null,
        retrieval_method: method,
        top_k: topK
      })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Query failed' }));
      throw new Error(err.detail || 'Query failed');
    }
    return res.json();
  }

  public static async verifyClaims(text: string, documentId?: string): Promise<VerificationResponseDTO> {
    const res = await fetch(`${API_BASE}/verify`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({
        text,
        document_id: documentId || null
      })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Verification failed' }));
      throw new Error(err.detail || 'Verification failed');
    }
    return res.json();
  }
}
