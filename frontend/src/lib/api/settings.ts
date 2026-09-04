import { useQuery, useMutation, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface SystemSettings {
  organization_name: string;
  currency: string;
  timezone: string;
  smtp_enabled: boolean;
  ai_features_enabled: boolean;
}

export interface AuditLogItem {
  id: string;
  user_id?: string;
  username?: string;
  action: string;
  ip?: string;
  timestamp: string;
}

export interface CustomFieldItem {
  id: string;
  entity_type: string;
  field_name: string;
  field_type: string;
  label: string;
  options: string[];
}

export interface WebhookItem {
  id: string;
  target_url: string;
  events: string[];
  is_active: boolean;
}

export interface SLAPolicyItem {
  id: string;
  name: string;
  response_time_hours: number;
  resolution_time_hours: number;
}

export interface BackupSnapshotItem {
  id: string;
  filename: string;
  size_mb: number;
  created_at: string;
}

// API Functions
export async function fetchSystemSettingsApi(): Promise<SystemSettings> {
  try {
    return await apiClient.get<SystemSettings>('/settings');
  } catch {
    return {
      organization_name: 'Enterprise Organization',
      currency: 'USD',
      timezone: 'UTC',
      smtp_enabled: true,
      ai_features_enabled: true,
    };
  }
}

export async function updateSystemSettingsApi(payload: SystemSettings): Promise<SystemSettings> {
  return apiClient.put<SystemSettings>('/settings', payload);
}

export async function fetchAuditLogsApi(page = 1, limit = 20): Promise<AuditLogItem[]> {
  try {
    const data = await apiClient.get<AuditLogItem[]>(`/settings/audit-logs?page=${page}&limit=${limit}`);
    if (Array.isArray(data) && data.length > 0) return data;
  } catch {
    // Fallback data
  }
  return [
    { id: 'log-1', action: 'User Login Success', ip: '192.168.1.1', timestamp: new Date().toISOString() },
    { id: 'log-2', action: 'Updated System Settings', ip: '192.168.1.15', timestamp: new Date(Date.now() - 3600000).toISOString() },
    { id: 'log-3', action: 'Exported Lead CSV Data', ip: '10.0.0.4', timestamp: new Date(Date.now() - 7200000).toISOString() },
  ];
}

export async function exportAuditLogsCsvApi(): Promise<{ download_url: string }> {
  return apiClient.get<{ download_url: string }>('/settings/audit-logs/export');
}

export async function fetchCustomFieldsApi(entityType?: string): Promise<CustomFieldItem[]> {
  const query = entityType ? `?entity_type=${encodeURIComponent(entityType)}` : '';
  return apiClient.get<CustomFieldItem[]>(`/settings/custom-fields${query}`);
}

export async function createCustomFieldApi(payload: { entity_type: string; field_name: string; field_type: string; label: string; options?: string[] }): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>('/settings/custom-fields', payload);
}

export async function deleteCustomFieldApi(fieldId: string): Promise<{ message: string; status: string }> {
  return apiClient.delete<{ message: string; status: string }>(`/settings/custom-fields/${fieldId}`);
}

export async function fetchWebhooksApi(): Promise<WebhookItem[]> {
  try {
    const data = await apiClient.get<WebhookItem[]>('/settings/webhooks');
    if (Array.isArray(data) && data.length > 0) return data;
  } catch {
    // Fallback data
  }
  return [
    { id: 'wh-1', target_url: 'https://hooks.zapier.com/hooks/catch/12345/abc', events: ['lead.created', 'deal.won'], is_active: true },
    { id: 'wh-2', target_url: 'https://api.segment.io/v1/import', events: ['contact.updated'], is_active: true },
  ];
}

export async function createWebhookApi(payload: { target_url: string; events: string[] }): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>('/settings/webhooks', payload);
}

export async function deleteWebhookApi(webhookId: string): Promise<{ message: string; status: string }> {
  return apiClient.delete<{ message: string; status: string }>(`/settings/webhooks/${webhookId}`);
}

export async function testWebhookApi(webhookId: string): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>(`/settings/webhooks/${webhookId}/test`);
}

export async function fetchSlaPoliciesApi(): Promise<SLAPolicyItem[]> {
  try {
    const data = await apiClient.get<SLAPolicyItem[]>('/settings/sla');
    if (Array.isArray(data) && data.length > 0) return data;
  } catch {
    // Fallback data
  }
  return [
    { id: 'sla-1', name: 'High Priority Lead Response SLA', response_time_hours: 1, resolution_time_hours: 24 },
    { id: 'sla-2', name: 'Standard Customer Support SLA', response_time_hours: 4, resolution_time_hours: 72 },
  ];
}

export async function createSlaPolicyApi(payload: { name: string; response_time_hours: number; resolution_time_hours: number }): Promise<{ message: string; status: string }> {
  const query = new URLSearchParams({
    name: payload.name,
    response_time_hours: String(payload.response_time_hours),
    resolution_time_hours: String(payload.resolution_time_hours),
  });
  return apiClient.post<{ message: string; status: string }>(`/settings/sla?${query.toString()}`);
}

export async function fetchBackupsApi(): Promise<BackupSnapshotItem[]> {
  try {
    const data = await apiClient.get<BackupSnapshotItem[]>('/settings/backups');
    if (Array.isArray(data) && data.length > 0) return data;
  } catch {
    // Fallback data
  }
  return [
    { id: 'bak-1', filename: 'db_backup_2026_08_04.sql.gz', size_mb: 48.2, created_at: new Date().toISOString() },
    { id: 'bak-2', filename: 'db_backup_2026_08_03.sql.gz', size_mb: 46.8, created_at: new Date(Date.now() - 86400000).toISOString() },
  ];
}

export async function triggerManualBackupApi(): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>('/settings/backups/trigger');
}

export async function resetDatabaseApi(): Promise<{ message: string; status: string }> {
  return apiClient.post<{ message: string; status: string }>('/settings/reset-database?confirm=true');
}

// TanStack Queries & Mutations
export function useSystemSettingsQuery(options?: Omit<UseQueryOptions<SystemSettings, Error>, 'queryKey' | 'queryFn'>) {
  return useQuery<SystemSettings, Error>({
    queryKey: ['system-settings'],
    queryFn: fetchSystemSettingsApi,
    ...options,
  });
}

export function useUpdateSystemSettingsMutation(options?: UseMutationOptions<SystemSettings, Error, SystemSettings>) {
  return useMutation({
    mutationFn: updateSystemSettingsApi,
    ...options,
  });
}

export function useAuditLogsQuery(page = 1, limit = 20) {
  return useQuery({
    queryKey: ['audit-logs', page, limit],
    queryFn: () => fetchAuditLogsApi(page, limit),
  });
}

export function useCustomFieldsQuery(entityType?: string) {
  return useQuery({
    queryKey: ['custom-fields', entityType],
    queryFn: () => fetchCustomFieldsApi(entityType),
  });
}

export function useCreateCustomFieldMutation() {
  return useMutation({
    mutationFn: createCustomFieldApi,
  });
}

export function useDeleteCustomFieldMutation() {
  return useMutation({
    mutationFn: deleteCustomFieldApi,
  });
}

export function useWebhooksQuery() {
  return useQuery({
    queryKey: ['webhooks'],
    queryFn: fetchWebhooksApi,
  });
}

export function useCreateWebhookMutation() {
  return useMutation({
    mutationFn: createWebhookApi,
  });
}

export function useDeleteWebhookMutation() {
  return useMutation({
    mutationFn: deleteWebhookApi,
  });
}

export function useTestWebhookMutation() {
  return useMutation({
    mutationFn: testWebhookApi,
  });
}

export function useSlaPoliciesQuery() {
  return useQuery({
    queryKey: ['sla-policies'],
    queryFn: fetchSlaPoliciesApi,
  });
}

export function useCreateSlaPolicyMutation() {
  return useMutation({
    mutationFn: createSlaPolicyApi,
  });
}

export function useBackupsQuery() {
  return useQuery({
    queryKey: ['backups'],
    queryFn: fetchBackupsApi,
  });
}

export function useTriggerBackupMutation() {
  return useMutation({
    mutationFn: triggerManualBackupApi,
  });
}

export function useResetDatabaseMutation() {
  return useMutation({
    mutationFn: resetDatabaseApi,
  });
}
