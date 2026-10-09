export type IssueCategory = 'GARBAGE' | 'DRAINAGE' | 'OTHER';
export type CaseStatus = 'OPEN' | 'MONITORING' | 'CLOSED';
export type VerificationState =
  | 'AWAITING_VERIFICATION'
  | 'CITIZEN_CONFIRMED_RESOLVED'
  | 'RESOLUTION_DISPUTED'
  | 'INSUFFICIENT_EVIDENCE';

export type TimelineOrigin =
  | 'SOURCE_FACT'
  | 'USER_CLAIM'
  | 'AI_RECOMMENDATION'
  | 'SYSTEM_EVENT';

export type RetrievalMethod =
  | 'USER_ENTERED'
  | 'IMPORTED_RECEIPT'
  | 'SCREENSHOT_OCR'
  | 'AUTHORISED_CONNECTOR'
  | 'MOCK';

export interface User {
  id: number;
  email: string;
  name: string;
  role: 'CITIZEN' | 'OFFICER' | 'ADMIN';
  created_at: string;
}

export interface ComplaintRecord {
  id: number;
  case_id: number;
  source: string;
  external_id?: string;
  raw_text: string;
  official_status: string;
  official_status_retrieved_at?: string;
  retrieval_method: RetrievalMethod;
  extracted_json: Record<string, any>;
  confidence: number;
  created_at: string;
}

export interface TimelineEvent {
  id: number;
  case_id: number;
  event_type: string;
  origin: TimelineOrigin;
  actor: string;
  source: string;
  payload_json: Record<string, any>;
  created_at: string;
}

export interface Case {
  id: number;
  user_id: number;
  title: string;
  issue_category: IssueCategory;
  location_text: string;
  lat?: number;
  lng?: number;
  ward: string;
  jurisdiction: string;
  status: CaseStatus;
  verification_state: VerificationState;
  created_at: string;
  updated_at: string;
  complaint_records?: ComplaintRecord[];
  timeline_events?: TimelineEvent[];
}
