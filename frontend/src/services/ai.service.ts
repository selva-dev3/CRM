import { apiClient } from '@/lib/api-client';

export interface LeadScoringResponse {
  score: number;
  reasoning: string;
}

export interface EmailGenerationResponse {
  subject: string;
  body: string;
}

export interface MeetingSummaryResponse {
  summary: string;
  actionItems: string[];
}

export const aiService = {
  getLeadScore: async (leadId: string): Promise<LeadScoringResponse> => {
    return apiClient<LeadScoringResponse>(`/ai/lead-scoring/${leadId}`);
  },

  generateEmail: async (prompt: string, context?: Record<string, unknown>): Promise<EmailGenerationResponse> => {
    return apiClient<EmailGenerationResponse>('/ai/generate-email', {
      method: 'POST',
      body: JSON.stringify({ prompt, context }),
    });
  },

  getSalesForecast: async () => {
    return apiClient('/ai/sales-forecast');
  },

  summarizeMeeting: async (transcript: string): Promise<MeetingSummaryResponse> => {
    return apiClient<MeetingSummaryResponse>('/ai/summarize-meeting', {
      method: 'POST',
      body: JSON.stringify({ transcript }),
    });
  },

  chatAssistant: async (message: string) => {
    return apiClient('/ai/chat', {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  },
};
