export interface VisaFitRequest {
  company: string;
  location: string;
  role: string;
  description: string;
}

export type Platform =
  | "workday"
  | "greenhouse"
  | "lever"
  | "linkedin"
  | "indeed"
  | "unknown";

export interface JobInfo {
  company: string;
  title: string;
  location: string;
  isRemote: boolean;
  platform: Platform;
  url: string;
  description: string;
}

export interface H1BRecord {
  year: number;
  approved: number;
  denied: number;
  initialApprovals: number;
}

export interface CompanyAnalysis {
  company: string;
  /** 0–100 score derived from USCIS filing history */
  sponsorScore: number;
  /** "sponsor" | "unlikely" | "unknown" */
  verdict: "sponsor" | "unlikely" | "unknown";
  h1bHistory: H1BRecord[];
  notes: string;
}

export interface AnalysisResponse {
  jobInfo: JobInfo;
  analysis: CompanyAnalysis;
}

export type MessageType =
  | { type: "JOB_DETECTED"; payload: JobInfo }
  | { type: "GET_JOB_INFO" }
  | { type: "JOB_INFO_RESPONSE"; payload: JobInfo | null }
  | { type: "AUTOFILL_REQUESTED"; payload: { fieldType: WorkAuthFieldType } };

export type WorkAuthFieldType =
  | "authorized"       // "Are you authorized to work in the US?"
  | "sponsorship"      // "Will you now or in the future require sponsorship?"
  | "visa_type";       // "What is your visa type?"

export interface PipelineEntry {
  id: string;
  jobInfo: JobInfo;
  analysis: CompanyAnalysis;
  appliedAt: string;
  status: "applied" | "screening" | "interviewing" | "offer" | "rejected" | "ghosted";
}
