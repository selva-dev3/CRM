import { apiClient } from '@/lib/api/client';

export interface AIEvidence {
  entity_type: string;
  entity_id: string;
  label: string;
  detail?: string | null;
}

export interface AIActionProposal {
  action_type: 'create_task' | 'draft_email' | 'update_record';
  title: string;
  payload: Record<string, unknown>;
  requires_confirmation: boolean;
  proposal_id?: string | null;
}

export interface AIActionExecutionResponse {
  proposal_id: string;
  action_type: string;
  status: 'executed';
  result: Record<string, unknown>;
}

export interface AIChatResponse {
  conversation_id: string;
  response: string;
  evidence: AIEvidence[];
  proposed_actions: AIActionProposal[];
  run_id?: string | null;
}

export interface LeadScoringResponse {
  lead_id: string;
  score: number;
  conversion_probability: number;
  quality: 'Hot' | 'Warm' | 'Cold';
  qualification: 'Qualified' | 'Needs Review' | 'Unqualified';
  confidence: number;
  reasons: string[];
}

export interface EmailGenerationResponse {
  subject: string;
  body: string;
  suggested_send_time?: string | null;
  rationale: string;
  evidence: AIEvidence[];
}

export interface MeetingSummaryResponse {
  summary: string;
  action_items: string[];
  decisions: string[];
  requirements: string[];
  objections: string[];
  competitors: string[];
  sentiment?: string | null;
}

export interface CRMSearchResponse {
  query: string;
  entity_type: 'lead' | 'contact' | 'company' | 'deal';
  result_count: number;
  results: Array<Record<string, unknown>>;
  explanation: string;
  run_id?: string | null;
}

export interface AIUsageStats {
  tokens_used_this_month: number;
  estimated_cost_usd: number;
  request_count: number;
  ai_credits_remaining?: number | null;
  monthly_cost_limit_usd?: number | null;
}

export const aiService = {
  getLeadScore: (leadId: string): Promise<LeadScoringResponse> =>
    apiClient.post<LeadScoringResponse>(
      `/ai/lead-scoring/evaluate?lead_id=${encodeURIComponent(leadId)}`,
    ),

  generateEmail: (
    prompt: string,
    context?: Record<string, unknown>,
  ): Promise<EmailGenerationResponse> =>
    apiClient.post<EmailGenerationResponse>('/ai/email-writer/generate', {
      prompt,
      context,
    }),

  summarizeMeeting: (transcript: string): Promise<MeetingSummaryResponse> =>
    apiClient.post<MeetingSummaryResponse>('/ai/call-summarizer/summarize', { transcript }),

  chatAssistant: (message: string, conversationId?: string): Promise<AIChatResponse> =>
    apiClient.post<AIChatResponse>('/ai/sales-assistant/chat', {
      message,
      conversation_id: conversationId,
    }),

  confirmAction: (proposalId: string): Promise<AIActionExecutionResponse> =>
    apiClient.post<AIActionExecutionResponse>('/ai/sales-assistant/actions/confirm', {
      proposal_id: proposalId,
    }),

  searchCRM: (
    query: string,
    scope: 'lead' | 'contact' | 'company' | 'deal',
  ): Promise<CRMSearchResponse> =>
    apiClient.post<CRMSearchResponse>('/ai/crm-search/query', { query, scope }),

  getUsageStats: (): Promise<AIUsageStats> =>
    apiClient.get<AIUsageStats>('/ai/usage-stats'),
};
