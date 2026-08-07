import { apiClient } from '@/lib/api-client';

export interface IntegrationItem {
  name: string;
  is_connected: boolean;
  last_synced?: string | null;
}

export interface ZapierConfig {
  name: string;
  is_connected: boolean;
  webhook_url?: string;
  events?: string[];
  last_synced?: string | null;
}

export async function fetchIntegrationsApi(): Promise<IntegrationItem[]> {
  try {
    const data = await apiClient.get<IntegrationItem[]>('/integrations');
    if (Array.isArray(data)) return data;
  } catch {
    // fallback
  }
  return [];
}

export async function connectIntegrationApi(name: string): Promise<{ message: string; auth_url?: string }> {
  return apiClient.post<{ message: string; auth_url?: string }>(`/integrations/${encodeURIComponent(name)}/connect`);
}

export async function disconnectIntegrationApi(name: string): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>(`/integrations/${encodeURIComponent(name)}/disconnect`);
}

export async function syncIntegrationApi(name: string): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>(`/integrations/${encodeURIComponent(name)}/sync`);
}

// Dedicated Zapier REST API Methods
export async function fetchZapierConfigApi(): Promise<ZapierConfig> {
  return apiClient.get<ZapierConfig>('/integrations/zapier');
}

export const DEFAULT_ZAPIER_WEBHOOK = process.env.NEXT_PUBLIC_ZAPIER_WEBHOOK_URL || 'https://hooks.zapier.com/hooks/catch/28479165/46abl1q';

export async function connectZapierApi(webhookUrl?: string): Promise<{ message: string }> {
  const url = webhookUrl || DEFAULT_ZAPIER_WEBHOOK;
  return apiClient.post<{ message: string }>('/integrations/zapier/connect', { webhook_url: url });
}

export async function testZapierPingApi(): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>('/integrations/zapier/test');
}

export async function triggerZapierEventApi(eventName: string, payload: any = {}): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>('/integrations/zapier/event', { event_name: eventName, payload });
}

export async function deleteZapierApi(): Promise<{ message: string }> {
  return apiClient.delete<{ message: string }>('/integrations/zapier');
}

export async function sendSlackNotifyApi(channel: string, message: string): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>('/integrations/slack/notify', { channel, message });
}

export async function saveCustomApiKeyApi(providerName: string, apiKey: string): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>('/integrations/custom-api-key', {
    provider_name: providerName,
    api_key: apiKey,
  });
}
