import { apiClient, openApiStream } from '@/lib/api/client';

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
  metadata?: {
    run_id?: string | null;
    provider?: string | null;
    model?: string | null;
    fallback_used: boolean;
    attempted_model_count: number;
    generated_at: string;
  } | null;
}

export interface AIConversationSummary {
  id: string;
  title: string;
  model_name: string;
  created_at: string;
  updated_at: string;
}

export interface AIConversationMessage {
  id: string;
  user_prompt: string;
  ai_response: string;
  result_blocks: AIResultBlock[];
  evidence: AIEvidence[];
  follow_up_questions: string[];
  provider?: string | null;
  model?: string | null;
  fallback_used: boolean;
  created_at: string;
}

export interface AIConversationDetail {
  id: string;
  title: string;
  messages: AIConversationMessage[];
}

export interface AIStreamHandlers {
  onStatus?: (message: string) => void;
  onDelta?: (text: string) => void;
  onFallback?: (message: string) => void;
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
  | 'user'
  | 'report';

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

  streamChatAssistant: async (
    message: string,
    conversationId: string | undefined,
    handlers: AIStreamHandlers,
    signal?: AbortSignal,
  ): Promise<AIChatResponse> => {
    const response = await openApiStream(
      '/ai/sales-assistant/chat/stream',
      { message, conversation_id: conversationId },
      signal,
    );
    if (!response.body) throw new Error('The AI response stream is unavailable.');
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let completed: AIChatResponse | undefined;
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const events = buffer.split('\n\n');
      buffer = events.pop() ?? '';
      for (const rawEvent of events) {
        const lines = rawEvent.split('\n');
        const eventName = lines.find((line) => line.startsWith('event:'))?.slice(6).trim();
        const dataText = lines.find((line) => line.startsWith('data:'))?.slice(5).trim();
        if (!eventName || !dataText) continue;
        const data = JSON.parse(dataText) as Record<string, unknown>;
        if (eventName === 'status') handlers.onStatus?.(String(data.message ?? 'Working'));
        if (eventName === 'fallback') handlers.onFallback?.(String(data.message ?? 'Model switched'));
        if (eventName === 'delta') handlers.onDelta?.(String(data.text ?? ''));
        if (eventName === 'complete') completed = data as unknown as AIChatResponse;
        if (eventName === 'error') throw new Error(String(data.message ?? 'The AI request failed.'));
      }
      if (done) break;
    }
    if (!completed) throw new Error('The AI response ended before completion.');
    return completed;
  },

  listConversations: (): Promise<AIConversationSummary[]> =>
    apiClient.get<AIConversationSummary[]>('/ai/sales-assistant/conversations'),

  getConversation: (conversationId: string): Promise<AIConversationDetail> =>
    apiClient.get<AIConversationDetail>(
      `/ai/sales-assistant/conversations/${encodeURIComponent(conversationId)}`,
    ),

  deleteConversation: (conversationId: string): Promise<{ message: string }> =>
    apiClient.delete<{ message: string }>(
      `/ai/sales-assistant/conversations/${encodeURIComponent(conversationId)}`,
    ),

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
