import { Case, ComplaintRecord, TimelineEvent, TimelineOrigin, VerificationState } from '../types';

const API_BASE = '/api/v1';

class ApiClient {
  private token: string | null = null;

  setToken(token: string) {
    this.token = token;
    localStorage.setItem('civicloop_token', token);
  }

  getToken(): string | null {
    if (!this.token) {
      this.token = localStorage.getItem('civicloop_token');
    }
    return this.token;
  }

  clearToken() {
    this.token = null;
    localStorage.removeItem('civicloop_token');
  }

  private getHeaders(): HeadersInit {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    const token = this.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  async login(email: string, password: string = 'Password123!') {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Login failed');
    }
    const data = await res.json();
    this.setToken(data.access_token);
    return data;
  }

  async getCurrentUser() {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error('Not authenticated');
    return res.json();
  }

  async getCases(status?: string): Promise<Case[]> {
    const url = status ? `${API_BASE}/cases?status=${status}` : `${API_BASE}/cases`;
    const res = await fetch(url, { headers: this.getHeaders() });
    if (!res.ok) throw new Error('Failed to fetch cases');
    return res.json();
  }

  async getCase(id: number): Promise<Case> {
    const res = await fetch(`${API_BASE}/cases/${id}`, { headers: this.getHeaders() });
    if (!res.ok) throw new Error('Failed to fetch case details');
    return res.json();
  }

  async createCase(data: {
    title: string;
    issue_category: 'GARBAGE' | 'DRAINAGE' | 'OTHER';
    location_text: string;
    ward: string;
    jurisdiction: string;
    initial_complaint_raw_text?: string;
  }): Promise<Case> {
    const res = await fetch(`${API_BASE}/cases`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to create case');
    }
    return res.json();
  }

  async getTimeline(caseId: number, origin?: TimelineOrigin): Promise<TimelineEvent[]> {
    const url = origin
      ? `${API_BASE}/cases/${caseId}/timeline?origin=${origin}`
      : `${API_BASE}/cases/${caseId}/timeline`;
    const res = await fetch(url, { headers: this.getHeaders() });
    if (!res.ok) throw new Error('Failed to fetch timeline');
    return res.json();
  }

  async transitionVerification(caseId: number, target_state: VerificationState, reason: string): Promise<Case> {
    const res = await fetch(`${API_BASE}/cases/${caseId}/transition-verification`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ target_state, reason }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail?.message || err.detail || 'Transition rejected');
    }
    return res.json();
  }

  async addComplaintRecord(caseId: number, data: {
    source: string;
    external_id?: string;
    raw_text: string;
    official_status: string;
    retrieval_method: string;
  }): Promise<ComplaintRecord> {
    const res = await fetch(`${API_BASE}/cases/${caseId}/complaints`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to append complaint record');
    return res.json();
  }

  async getAIHealth() {
    const res = await fetch('/api/ai/health');
    if (!res.ok) return { status: 'unknown', agent_model: 'DeepSeek V4', vision_model: 'Qwen 3.6 VL', embed_model: 'BGE-M3' };
    return res.json();
  }

  async extractFromText(text: string) {
    const res = await fetch(`${API_BASE}/ai/extract/text`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ text }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Extraction failed');
    }
    return res.json();
  }

  async extractFromScreenshot(imageUrl: string) {
    const res = await fetch(`${API_BASE}/ai/extract/screenshot`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ image_url: imageUrl }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Vision extraction failed');
    }
    return res.json();
  }

  async findCaseLinks(payload: {
    category: string;
    location_text: string;
    lat?: number;
    lng?: number;
    ward?: string;
  }) {
    const res = await fetch(`${API_BASE}/case-linking/find-links`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Failed to search candidate cases');
    return res.json();
  }

  async linkComplaintToCase(complaintId: number, targetCaseId: number, reason?: string) {
    const res = await fetch(`${API_BASE}/case-linking/link-complaint`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({
        complaint_id: complaintId,
        target_case_id: targetCaseId,
        reason,
      }),
    });
    if (!res.ok) throw new Error('Failed to link complaint to case');
    return res.json();
  }
}

export const api = new ApiClient();

