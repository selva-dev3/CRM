import { apiClient } from '@/lib/api/client';

export interface IntegrationItem {
  name: string;
  is_connected: boolean;
  last_synced?: string | null;
}

export interface ApiKeyItem {
  id: string;
  name: string;
  api_key?: string | null;
  key?: string | null;
  created_at: string;
  last_used?: string | null;
  is_active: boolean;
}

export interface ZapierConfig {
  name: string;
  is_connected: boolean;
  webhook_url?: string;
  events?: string[];
  last_synced?: string | null;
}

export interface SlackConfig {
  name: string;
  is_connected: boolean;
  webhook_url?: string;
  events?: string[];
  last_synced?: string | null;
}

export interface MailchimpConnectPayload {
  api_key: string;
  server_prefix: string;
  audience_id: string;
}

export async function fetchIntegrationsApi(): Promise<IntegrationItem[]> {
  return apiClient.get<IntegrationItem[]>('/integrations');
}

export async function fetchApiKeysApi(): Promise<ApiKeyItem[]> {
  return apiClient.get<ApiKeyItem[]>('/auth/api-keys');
}

export async function createApiKeyApi(name: string): Promise<ApiKeyItem> {
  return apiClient.post<ApiKeyItem>('/auth/api-keys', { name });
}

export async function revokeApiKeyApi(keyId: string): Promise<{ message: string }> {
  return apiClient.delete<{ message: string }>(`/auth/api-keys/${encodeURIComponent(keyId)}`);
}

export async function connectIntegrationApi(name: string): Promise<{ message: string; auth_url?: string }> {
  const oauthPaths: Record<string, string> = {
    'google-calendar': '/integrations/google/connect',
    hubspot: '/integrations/hubspot/connect',
    'slack-sync': '/integrations/slack/oauth/connect',
  };
  const path = oauthPaths[name];
  if (!path) throw new Error(`OAuth is not supported for ${name}.`);
  return apiClient.get<{ message: string; auth_url?: string }>(path);
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

export async function connectZapierApi(webhookUrl?: string): Promise<{ message: string }> {
  if (!webhookUrl?.trim()) throw new Error('Zapier webhook URL is required.');
  return apiClient.post<{ message: string }>('/integrations/zapier/connect', {
    webhook_url: webhookUrl.trim(),
  });
}

export async function connectMailchimpApi(payload: MailchimpConnectPayload): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>('/integrations/mailchimp/connect', payload);
}

export async function deleteMailchimpApi(): Promise<{ message: string }> {
  return apiClient.delete<{ message: string }>('/integrations/mailchimp');
}

export async function testZapierPingApi(): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>('/integrations/zapier/test');
}

export async function triggerZapierEventApi(eventName: string, payload: Record<string, unknown> = {}): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>('/integrations/zapier/event', { event_name: eventName, payload });
}

export async function deleteZapierApi(): Promise<{ message: string }> {
  return apiClient.delete<{ message: string }>('/integrations/zapier');
}

// Dedicated Slack REST API Methods
export async function fetchSlackConfigApi(): Promise<SlackConfig> {
  return apiClient.get<SlackConfig>('/integrations/slack');
}

export async function connectSlackApi(webhookUrl: string): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>('/integrations/slack/connect', { webhook_url: webhookUrl });
}

export async function updateSlackEventsApi(events: string[]): Promise<{ message: string }> {
  return apiClient.put<{ message: string }>('/integrations/slack/events', { events });
}

export async function testSlackConnectionApi(): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>('/integrations/slack/test');
}

export async function deleteSlackApi(): Promise<{ message: string }> {
  return apiClient.delete<{ message: string }>('/integrations/slack');
}

export async function sendSlackNotifyApi(channel: string, message: string): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>('/integrations/slack/notify', { channel, message });
}
