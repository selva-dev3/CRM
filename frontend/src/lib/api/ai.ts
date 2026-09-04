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
  result_blocks?: AIResultBlock[];
  follow_up_questions?: string[];
  run_id?: string | null;
}

export type CRMEntityType =
  | 'lead'
  | 'contact'
  | 'company'
  | 'deal'
  | 'task'
  | 'project'
  | 'call'
  | 'meeting'
  | 'email'
  | 'note'
  | 'document'
  | 'product'
  | 'quote'
  | 'invoice'
  | 'calendar_event'
  | 'activity'
  | 'user';

export interface AIResultBlock {
  key: string;
  title: string;
  entity_type: string;
  intent: string;
  results: Array<Record<string, unknown>>;
  result_count: number;
  explanation: string;
  generated_at: string;
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

export interface CRMSearchPlan {
  intent: 'list' | 'detail' | 'count' | 'aggregate' | 'comparison';
  entity_type: CRMEntityType;
  text_query?: string | null;
  status?: string | null;
  filters: Array<{
    field: string;
    operator: 'equals' | 'contains' | 'gte' | 'lte' | 'before' | 'after';
    value: string | number | boolean;
  }>;
  include_fields?: string[];
  aggregate?: 'sum' | 'average' | 'minimum' | 'maximum' | null;
  aggregate_field?: string | null;
  group_by?: string | null;
  date_field?: string | null;
  date_range?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  sort_by?: string | null;
  sort_direction: 'asc' | 'desc';
  inactive_days?: number | null;
  minimum_open_deal_amount?: number | null;
  limit: number;
}

export interface CRMSearchResponse {
  query: string;
  plan: CRMSearchPlan;
  result_count: number;
  results: Array<Record<string, unknown>>;
  explanation: string;
  run_id: string;
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
    scope?: 'lead' | 'contact' | 'company' | 'deal' | 'task' | 'project',
  ): Promise<CRMSearchResponse> =>
    apiClient.post<CRMSearchResponse>('/ai/crm-search/query', {
      query,
      ...(scope ? { scope } : {}),
    }),

  getUsageStats: (): Promise<AIUsageStats> =>
    apiClient.get<AIUsageStats>('/ai/usage-stats'),
};
