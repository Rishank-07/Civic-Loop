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
}

export const api = new ApiClient();
