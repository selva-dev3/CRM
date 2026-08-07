import { apiClient } from '@/lib/api-client';

export interface IntegrationItem {
  name: string;
  is_connected: boolean;
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

export async function sendSlackNotifyApi(channel: string, message: string): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>('/integrations/slack/notify', { channel, message });
}

export async function saveCustomApiKeyApi(providerName: string, apiKey: string): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>('/integrations/custom-api-key', {
    provider_name: providerName,
    api_key: apiKey,
  });
}
