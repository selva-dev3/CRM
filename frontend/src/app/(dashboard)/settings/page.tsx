'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  Settings as SettingsIcon,
  Globe,
  Sliders,
  Webhook as WebhookIcon,
  ShieldAlert,
  Database,
  Plus,
  Trash2,
  Send,
  Save,
  CheckCircle2,
  AlertCircle,
  Clock,
  Cpu,
  Mail,
  RefreshCw,
  FileSpreadsheet,
  Building,
  Layers,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { CustomSelect } from '@/components/common/custom-select';
import { ModalShell } from '@/components/common/modal-shell';
import { PermissionGate } from '@/components/common/permission-gate';
import { PERMISSIONS } from '@/lib/permissions';
import {
  useSystemSettingsQuery,
  useUpdateSystemSettingsMutation,
  useAuditLogsQuery,
  exportAuditLogsCsvApi,
  useCustomFieldsQuery,
  useCreateCustomFieldMutation,
  useDeleteCustomFieldMutation,
  useWebhooksQuery,
  useCreateWebhookMutation,
  useDeleteWebhookMutation,
  useTestWebhookMutation,
  useSlaPoliciesQuery,
  useCreateSlaPolicyMutation,
  useBackupsQuery,
  useTriggerBackupMutation,
  useResetDatabaseMutation,
  CustomFieldItem,
  WebhookItem,
  SLAPolicyItem,
  BackupSnapshotItem
} from '@/lib/api/settings';

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<'general' | 'fields' | 'webhooks' | 'sla' | 'backups' | 'audit'>('general');
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Queries
  const { data: settings, refetch: refetchSettings } = useSystemSettingsQuery();
  const { data: customFields = [], refetch: refetchFields } = useCustomFieldsQuery();
  const { data: webhooks = [], refetch: refetchWebhooks } = useWebhooksQuery();
  const { data: slaPolicies = [], refetch: refetchSla } = useSlaPoliciesQuery();
  const { data: backups = [], refetch: refetchBackups } = useBackupsQuery();
  const { data: auditLogs = [] } = useAuditLogsQuery();

  // Mutations
  const updateSettingsMutation = useUpdateSystemSettingsMutation();
  const createCustomFieldMutation = useCreateCustomFieldMutation();
  const deleteCustomFieldMutation = useDeleteCustomFieldMutation();
  const createWebhookMutation = useCreateWebhookMutation();
  const deleteWebhookMutation = useDeleteWebhookMutation();
  const testWebhookMutation = useTestWebhookMutation();
  const createSlaMutation = useCreateSlaPolicyMutation();
  const triggerBackupMutation = useTriggerBackupMutation();
  const resetDatabaseMutation = useResetDatabaseMutation();

  // Form States
  const [orgName, setOrgName] = useState('Enterprise Organization');
  const [currency, setCurrency] = useState('USD');
  const [timezone, setTimezone] = useState('UTC');
  const [smtpEnabled, setSmtpEnabled] = useState(true);
  const [aiEnabled, setAiEnabled] = useState(true);

  // Modals
  const [isFieldModalOpen, setIsFieldModalOpen] = useState(false);
  const [fieldEntityType, setFieldEntityType] = useState('Lead');
  const [fieldName, setFieldName] = useState('');
  const [fieldType, setFieldType] = useState('text');
  const [fieldLabel, setFieldLabel] = useState('');
  const [fieldOptions, setFieldOptions] = useState('');

  const [isWebhookModalOpen, setIsWebhookModalOpen] = useState(false);
  const [webhookUrl, setWebhookUrl] = useState('');
  const [webhookEvents, setWebhookEvents] = useState('lead.created,deal.won');

  const [isSlaModalOpen, setIsSlaModalOpen] = useState(false);
  const [slaName, setSlaName] = useState('');
  const [slaResponseTime, setSlaResponseTime] = useState('1');
  const [slaResolutionTime, setSlaResolutionTime] = useState('24');

  // Delete Confirm Modal State
  const [isResetDbModalOpen, setIsResetDbModalOpen] = useState(false);
  const [itemToDelete, setItemToDelete] = useState<{ type: 'field' | 'webhook'; id: string; name: string } | null>(null);

  // Synchronize Settings Form when loaded
  React.useEffect(() => {
    if (settings) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- hydrate editable settings from API data
      setOrgName(settings.organization_name || 'Enterprise Organization');
      setCurrency(settings.currency || 'USD');
      setTimezone(settings.timezone || 'UTC');
      setSmtpEnabled(settings.smtp_enabled ?? true);
      setAiEnabled(settings.ai_features_enabled ?? true);
    }
  }, [settings]);

  // Handlers
  const handleSaveGeneralSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setErrorMessage(null);
      await updateSettingsMutation.mutateAsync({
        organization_name: orgName,
        currency,
        timezone,
        smtp_enabled: smtpEnabled,
        ai_features_enabled: aiEnabled,
      });
      setSuccessMessage('System settings updated successfully.');
      refetchSettings();
    } catch {
      setErrorMessage('Failed to update system settings.');
    }
  };

  const handleCreateCustomField = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fieldName || !fieldLabel) {
      setErrorMessage('Please fill in field name and label.');
      return;
    }
    try {
      setErrorMessage(null);
      const res = await createCustomFieldMutation.mutateAsync({
        entity_type: fieldEntityType,
        field_name: fieldName,
        field_type: fieldType,
        label: fieldLabel,
        options: fieldType === 'select'
          ? fieldOptions.split(',').map((option) => option.trim()).filter(Boolean)
          : [],
      });
      setSuccessMessage(res.message || `Custom field '${fieldLabel}' added successfully.`);
      setIsFieldModalOpen(false);
      setFieldName('');
      setFieldLabel('');
      setFieldOptions('');
      refetchFields();
    } catch {
      setErrorMessage('Failed to create custom field.');
    }
  };

  const handleCreateWebhook = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!webhookUrl) {
      setErrorMessage('Please enter target webhook URL.');
      return;
    }
    try {
      setErrorMessage(null);
      const eventsList = webhookEvents.split(',').map((e) => e.trim());
      const res = await createWebhookMutation.mutateAsync({
        target_url: webhookUrl,
        events: eventsList,
      });
      setSuccessMessage(res.message || `Webhook registered for ${webhookUrl}`);
      setIsWebhookModalOpen(false);
      setWebhookUrl('');
      refetchWebhooks();
    } catch {
      setErrorMessage('Failed to create webhook.');
    }
  };

  const handleTestWebhook = async (id: string) => {
    try {
      setErrorMessage(null);
      const res = await testWebhookMutation.mutateAsync(id);
      setSuccessMessage(res.message || 'Test payload sent to webhook URL.');
    } catch {
      setErrorMessage('Failed to send test ping payload.');
    }
  };

  const handleCreateSla = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!slaName) {
      setErrorMessage('Please enter SLA policy name.');
      return;
    }
    try {
      setErrorMessage(null);
      const res = await createSlaMutation.mutateAsync({
        name: slaName,
        response_time_hours: parseInt(slaResponseTime) || 1,
        resolution_time_hours: parseInt(slaResolutionTime) || 24,
      });
      setSuccessMessage(res.message || `SLA policy '${slaName}' created successfully.`);
      setIsSlaModalOpen(false);
      setSlaName('');
      refetchSla();
    } catch {
      setErrorMessage('Failed to create SLA policy.');
    }
  };

  const handleTriggerBackup = async () => {
    try {
      setErrorMessage(null);
      const res = await triggerBackupMutation.mutateAsync();
      setSuccessMessage(res.message || 'Database snapshot backup triggered successfully.');
      refetchBackups();
    } catch {
      setErrorMessage('Failed to trigger manual database backup.');
    }
  };

  const handleConfirmDeleteItem = async () => {
    if (!itemToDelete) return;
    try {
      setErrorMessage(null);
      if (itemToDelete.type === 'field') {
        const res = await deleteCustomFieldMutation.mutateAsync(itemToDelete.id);
        setSuccessMessage(res.message || `Custom field '${itemToDelete.name}' deleted.`);
        refetchFields();
      } else {
        const res = await deleteWebhookMutation.mutateAsync(itemToDelete.id);
        setSuccessMessage(res.message || `Webhook '${itemToDelete.name}' deleted.`);
        refetchWebhooks();
      }
      setItemToDelete(null);
    } catch {
      setErrorMessage('Failed to delete item.');
      setItemToDelete(null);
    }
  };

  const handleConfirmResetDb = async () => {
    try {
      setErrorMessage(null);
      const res = await resetDatabaseMutation.mutateAsync();
      setSuccessMessage(res.message || 'Database reset successfully.');
      setIsResetDbModalOpen(false);
    } catch {
      setErrorMessage('Database reset failed.');
      setIsResetDbModalOpen(false);
    }
  };

  const handleExportAuditLogs = async () => {
    try {
      setErrorMessage(null);
      const res = await exportAuditLogsCsvApi();
      if (res?.download_url) {
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = res.download_url;
        a.download = `audit_logs_${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
          if (document.body.contains(a)) {
            document.body.removeChild(a);
          }
        }, 150);
        setSuccessMessage('Audit trail CSV downloaded successfully!');
      } else {
        setSuccessMessage('Audit trail CSV generated.');
      }
    } catch {
      setErrorMessage('Failed to export audit logs CSV.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 w-full">
        <div className="min-w-0 flex-1">
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900 flex items-center gap-2.5 break-words">
            <SettingsIcon className="w-5 h-5 sm:w-6 sm:h-6 text-blue-600 shrink-0" />
            <span>System Settings & Governance</span>
          </h1>
          <p className="text-xs font-medium text-slate-500 mt-1">
            Configure system defaults, metadata schemas, webhook subscriptions, SLA policies, and database maintenance.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 sm:gap-3 w-full sm:w-auto shrink-0">
          <PermissionGate permission={PERMISSIONS.ORGANIZATION.READ}>
            <Link
              href="/organization"
              className="flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-xl text-xs font-bold transition shadow-xs cursor-pointer w-full sm:w-auto"
            >
              <Building className="w-4 h-4 shrink-0" />
              <span>Organization Settings</span>
            </Link>
          </PermissionGate>

          <PermissionGate permission={PERMISSIONS.INTEGRATIONS.READ}>
            <Link
              href="/integrations"
              className="flex items-center justify-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-4 py-2 rounded-xl text-xs font-bold transition shadow-xs cursor-pointer w-full sm:w-auto"
            >
              <Layers className="w-4 h-4 text-indigo-600 shrink-0" />
              <span>Integrations</span>
            </Link>
          </PermissionGate>
        </div>
      </div>

      {/* Feedback Alert Banners */}
      {successMessage && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-sm font-medium flex items-center gap-2 animate-in fade-in-50">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-sm font-medium flex items-center gap-2 animate-in fade-in-50">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Navigation Sub-Tabs */}
      <div className="flex items-center border-b border-slate-200 gap-6 text-sm font-semibold text-slate-600 overflow-x-auto">
        <button
          onClick={() => setActiveTab('general')}
          className={`pb-3 cursor-pointer transition border-b-2 shrink-0 flex items-center gap-1.5 ${
            activeTab === 'general' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <Globe className="w-4 h-4" />
          <span>General Settings</span>
        </button>

        <button
          onClick={() => setActiveTab('fields')}
          className={`pb-3 cursor-pointer transition border-b-2 shrink-0 flex items-center gap-1.5 ${
            activeTab === 'fields' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <Sliders className="w-4 h-4" />
          <span>Custom Metadata Fields</span>
        </button>

        <button
          onClick={() => setActiveTab('webhooks')}
          className={`pb-3 cursor-pointer transition border-b-2 shrink-0 flex items-center gap-1.5 ${
            activeTab === 'webhooks' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <WebhookIcon className="w-4 h-4" />
          <span>Webhooks & Integration</span>
        </button>

        <button
          onClick={() => setActiveTab('sla')}
          className={`pb-3 cursor-pointer transition border-b-2 shrink-0 flex items-center gap-1.5 ${
            activeTab === 'sla' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <Clock className="w-4 h-4" />
          <span>SLA Policies</span>
        </button>

        <button
          onClick={() => setActiveTab('backups')}
          className={`pb-3 cursor-pointer transition border-b-2 shrink-0 flex items-center gap-1.5 ${
            activeTab === 'backups' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          <Database className="w-4 h-4" />
          <span>Database & Maintenance</span>
        </button>

        <PermissionGate permission={PERMISSIONS.SETTINGS.SECURITY}>
          <button
            onClick={() => setActiveTab('audit')}
            className={`pb-3 cursor-pointer transition border-b-2 shrink-0 flex items-center gap-1.5 ${
              activeTab === 'audit' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
            }`}
          >
            <ShieldAlert className="w-4 h-4" />
            <span>Security Audit Trail</span>
          </button>
        </PermissionGate>
      </div>

      {/* TAB 1: GENERAL SYSTEM SETTINGS */}
      {activeTab === 'general' && (
        <Card className="p-6 border border-slate-200 bg-white shadow-sm rounded-xl space-y-6 max-w-2xl">
          <h3 className="font-bold text-slate-900 text-base flex items-center gap-2 border-b border-slate-100 pb-3">
            <Globe className="w-4 h-4 text-blue-600" />
            <span>General System Preferences</span>
          </h3>

          <form onSubmit={handleSaveGeneralSettings} className="space-y-4 text-xs">
            <div className="space-y-1">
              <Label className="text-slate-700 font-semibold">Primary Organization Name</Label>
              <Input
                type="text"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                className="h-9 text-xs"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label className="text-slate-700 font-semibold">Default Currency</Label>
                <CustomSelect
                  value={currency}
                  onChange={setCurrency}
                  options={[
                    { value: 'USD', label: 'USD ($)' },
                    { value: 'EUR', label: 'EUR (€)' },
                    { value: 'GBP', label: 'GBP (£)' },
                    { value: 'INR', label: 'INR (₹)' },
                  ]}
                />
              </div>

              <div className="space-y-1">
                <Label className="text-slate-700 font-semibold">System Timezone</Label>
                <CustomSelect
                  value={timezone}
                  onChange={setTimezone}
                  options={[
                    { value: 'UTC', label: 'UTC (Coordinated Universal Time)' },
                    { value: 'EST', label: 'EST (Eastern Standard Time)' },
                    { value: 'PST', label: 'PST (Pacific Standard Time)' },
                    { value: 'IST', label: 'IST (Indian Standard Time)' },
                  ]}
                />
              </div>
            </div>

            <div className="pt-2 space-y-3">
              <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg border border-slate-200">
                <div className="flex items-center gap-2.5">
                  <Mail className="w-4 h-4 text-blue-600" />
                  <div>
                    <div className="font-bold text-slate-900">SMTP Email Delivery Service</div>
                    <div className="text-[11px] text-slate-500">Enable Brevo/SendGrid transactional email system</div>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={smtpEnabled}
                  onChange={(e) => setSmtpEnabled(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                />
              </div>

              <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg border border-slate-200">
                <div className="flex items-center gap-2.5">
                  <Cpu className="w-4 h-4 text-purple-600" />
                  <div>
                    <div className="font-bold text-slate-900 font-sans">AI Sales Assistant & Lead Scoring</div>
                    <div className="text-[11px] text-slate-500">Enable automated deal predictions & smart summary generation</div>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={aiEnabled}
                  onChange={(e) => setAiEnabled(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                />
              </div>
            </div>

            <div className="pt-3">
              <PermissionGate permission={PERMISSIONS.SETTINGS.UPDATE}>
                <Button
                  type="submit"
                  disabled={updateSettingsMutation.isPending}
                  className="bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs gap-1.5 cursor-pointer"
                >
                  <Save className="w-4 h-4" />
                  <span>{updateSettingsMutation.isPending ? 'Saving...' : 'Save General Settings'}</span>
                </Button>
              </PermissionGate>
            </div>
          </form>
        </Card>
      )}

      {/* TAB 2: CUSTOM METADATA FIELDS */}
      {activeTab === 'fields' && (
        <Card className="p-4 sm:p-6 border border-slate-200 bg-white shadow-sm rounded-xl space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
            <h3 className="font-bold text-slate-900 text-sm sm:text-base flex items-center gap-2">
              <Sliders className="w-4 h-4 text-blue-600 shrink-0" />
              <span>Custom Schema Fields</span>
            </h3>
            <PermissionGate permission={PERMISSIONS.SETTINGS.UPDATE}>
              <Button
                size="sm"
                onClick={() => setIsFieldModalOpen(true)}
                className="bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs gap-1 cursor-pointer w-full sm:w-auto"
              >
                <Plus className="w-4 h-4 shrink-0" />
                <span>Add Custom Field</span>
              </Button>
            </PermissionGate>
          </div>

          <div className="space-y-3">
            {customFields.length > 0 ? (
              customFields.map((f: CustomFieldItem) => (
                <div key={f.id} className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                  <div className="space-y-0.5 min-w-0 flex-1">
                    <div className="font-bold text-slate-900 flex flex-wrap items-center gap-2">
                      <span className="break-words">{f.label}</span>
                      <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200 text-[10px] shrink-0">
                        {f.entity_type}
                      </Badge>
                    </div>
                    <div className="text-[11px] text-slate-500 font-mono break-all">
                      key: <span className="font-bold text-slate-700">{f.field_name}</span> ({f.field_type})
                    </div>
                  </div>

                  <PermissionGate permission={PERMISSIONS.SETTINGS.UPDATE}>
                    <button
                      type="button"
                      onClick={() => setItemToDelete({ type: 'field', id: f.id, name: f.label })}
                      className="p-1 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded transition cursor-pointer self-end sm:self-auto shrink-0"
                      title="Delete field"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </PermissionGate>
                </div>
              ))
            ) : (
              <div className="text-xs text-slate-500 p-6 text-center bg-slate-50 rounded-lg">No custom fields created</div>
            )}
          </div>
        </Card>
      )}

      {/* TAB 3: WEBHOOKS */}
      {activeTab === 'webhooks' && (
        <Card className="p-4 sm:p-6 border border-slate-200 bg-white shadow-sm rounded-xl space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
            <h3 className="font-bold text-slate-900 text-sm sm:text-base flex items-center gap-2">
              <WebhookIcon className="w-4 h-4 text-blue-600 shrink-0" />
              <span>Outgoing Webhook Subscriptions</span>
            </h3>
            <PermissionGate permission={PERMISSIONS.SETTINGS.UPDATE}>
              <Button
                size="sm"
                onClick={() => setIsWebhookModalOpen(true)}
                className="bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs gap-1 cursor-pointer w-full sm:w-auto"
              >
                <Plus className="w-4 h-4 shrink-0" />
                <span>Register Webhook</span>
              </Button>
            </PermissionGate>
          </div>

          <div className="space-y-3">
            {webhooks.length > 0 ? (
              webhooks.map((w: WebhookItem) => (
                <div key={w.id} className="p-3.5 sm:p-4 bg-slate-50 rounded-lg border border-slate-200 space-y-2.5 text-xs">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 sm:gap-4">
                    <div className="font-mono font-bold text-slate-900 break-all sm:truncate sm:max-w-md min-w-0">
                      {w.target_url}
                    </div>
                    <div className="flex items-center justify-between sm:justify-start gap-2 w-full sm:w-auto shrink-0 pt-1.5 sm:pt-0 border-t sm:border-t-0 border-slate-200/60">
                      <PermissionGate permission={PERMISSIONS.SETTINGS.UPDATE}>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleTestWebhook(w.id)}
                          disabled={testWebhookMutation.isPending}
                          className="h-7 text-[11px] font-semibold border-slate-300 cursor-pointer w-full sm:w-auto"
                        >
                          <Send className="w-3 h-3 mr-1 text-blue-600 shrink-0" />
                          <span>Test Ping</span>
                        </Button>
                      </PermissionGate>

                      <PermissionGate permission={PERMISSIONS.SETTINGS.UPDATE}>
                        <button
                          type="button"
                          onClick={() => setItemToDelete({ type: 'webhook', id: w.id, name: w.target_url })}
                          className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition cursor-pointer shrink-0"
                          title="Delete webhook"
                          aria-label="Delete webhook"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </PermissionGate>
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-1.5 pt-0.5">
                    {w.events.map((ev) => (
                      <span key={ev} className="px-2 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 rounded text-[10px] font-semibold break-all">
                        {ev}
                      </span>
                    ))}
                  </div>
                </div>
              ))
            ) : (
              <div className="text-xs text-slate-500 p-4 sm:p-6 text-center bg-slate-50 rounded-lg border border-dashed border-slate-200">
                No registered webhooks
              </div>
            )}
          </div>
        </Card>
      )}

      {/* TAB 4: SLA POLICIES */}
      {activeTab === 'sla' && (
        <Card className="p-4 sm:p-6 border border-slate-200 bg-white shadow-sm rounded-xl space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
            <h3 className="font-bold text-slate-900 text-sm sm:text-base flex items-center gap-2">
              <Clock className="w-4 h-4 text-blue-600 shrink-0" />
              <span>Response & Resolution SLA Policies</span>
            </h3>
            <PermissionGate permission={PERMISSIONS.SETTINGS.UPDATE}>
              <Button
                size="sm"
                onClick={() => setIsSlaModalOpen(true)}
                className="bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs gap-1 cursor-pointer w-full sm:w-auto"
              >
                <Plus className="w-4 h-4 shrink-0" />
                <span>Create SLA Policy</span>
              </Button>
            </PermissionGate>
          </div>

          <div className="space-y-3">
            {slaPolicies.length > 0 ? (
              slaPolicies.map((s: SLAPolicyItem) => (
                <div key={s.id} className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                  <div className="min-w-0 flex-1">
                    <div className="font-bold text-slate-900 break-words">{s.name}</div>
                    <div className="text-[11px] text-slate-500">
                      Response Target: <span className="font-bold text-slate-800">{s.response_time_hours} hrs</span> | Resolution Target: <span className="font-bold text-slate-800">{s.resolution_time_hours} hrs</span>
                    </div>
                  </div>
                  <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200 text-xs self-start sm:self-auto shrink-0">
                    Active SLA
                  </Badge>
                </div>
              ))
            ) : (
              <div className="text-xs text-slate-500 p-6 text-center bg-slate-50 rounded-lg">No SLA policies defined</div>
            )}
          </div>
        </Card>
      )}

      {/* TAB 5: BACKUPS & DATABASE RESET */}
      {activeTab === 'backups' && (
        <div className="space-y-6">
          <Card className="p-4 sm:p-6 border border-slate-200 bg-white shadow-sm rounded-xl space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-sm sm:text-base flex items-center gap-2">
                <Database className="w-4 h-4 text-blue-600 shrink-0" />
                <span>Automated Database Backup Snapshots</span>
              </h3>
              <PermissionGate permission={PERMISSIONS.SETTINGS.UPDATE}>
                <Button
                  size="sm"
                  onClick={handleTriggerBackup}
                  disabled={triggerBackupMutation.isPending}
                  className="bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs gap-1.5 cursor-pointer w-full sm:w-auto"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${triggerBackupMutation.isPending ? 'animate-spin' : ''}`} />
                  <span>Trigger Manual Backup</span>
                </Button>
              </PermissionGate>
            </div>

            <div className="space-y-2">
              {backups.map((b: BackupSnapshotItem) => (
                <div key={b.id} className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <Database className="w-4 h-4 text-slate-400 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="font-mono font-bold text-slate-900 break-all">{b.filename}</div>
                      <div className="text-[10px] text-slate-400">{new Date(b.created_at).toLocaleString()}</div>
                    </div>
                  </div>
                  <Badge variant="outline" className="bg-slate-100 text-slate-700 border-slate-300 text-xs font-mono self-start sm:self-auto shrink-0">
                    {b.size_mb} MB
                  </Badge>
                </div>
              ))}
            </div>
          </Card>

          {/* DANGER ZONE: RESET DATABASE */}
          <Card className="p-4 sm:p-6 border border-rose-200 bg-rose-50/40 shadow-sm rounded-xl space-y-3">
            <div className="flex items-center gap-2 text-rose-700 font-bold text-base">
              <ShieldAlert className="w-5 h-5 shrink-0" />
              <span>Danger Zone: Database Maintenance</span>
            </div>
            <p className="text-xs text-slate-600">
              Truncate all system tables and reset database back to factory clean state (Preserves superadmin user).
            </p>
            <div>
              <PermissionGate permission={PERMISSIONS.SETTINGS.UPDATE}>
                <Button
                  size="sm"
                  onClick={() => setIsResetDbModalOpen(true)}
                  className="bg-rose-600 hover:bg-rose-700 text-white font-semibold text-xs gap-1.5 cursor-pointer w-full sm:w-auto"
                >
                  <Trash2 className="w-4 h-4" />
                  <span>Reset System Database</span>
                </Button>
              </PermissionGate>
            </div>
          </Card>
        </div>
      )}

      {/* TAB 6: SECURITY AUDIT TRAIL LOGS */}
      {activeTab === 'audit' && (
        <Card className="p-4 sm:p-6 border border-slate-200 bg-white shadow-sm rounded-xl space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
            <h3 className="font-bold text-slate-900 text-sm sm:text-base flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-blue-600 shrink-0" />
              <span>Security & User Activity Audit Trail</span>
            </h3>
            <PermissionGate permission={PERMISSIONS.SETTINGS.SECURITY}>
              <Button
                size="sm"
                variant="outline"
                onClick={handleExportAuditLogs}
                className="border-slate-300 font-semibold text-xs gap-1.5 cursor-pointer w-full sm:w-auto"
              >
                <FileSpreadsheet className="w-4 h-4 text-emerald-600" />
                <span>Export Audit CSV</span>
              </Button>
            </PermissionGate>
          </div>

          <div className="space-y-2 text-xs">
            {auditLogs.map((log) => (
              <div key={log.id} className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="min-w-0 flex-1 space-y-0.5">
                  <div className="font-bold text-slate-900 break-words">{log.action}</div>
                  <div className="text-[11px] text-slate-500 font-mono break-all">
                    User: {log.username || log.user_id || 'Admin User'} | IP: {log.ip || '127.0.0.1'}
                  </div>
                </div>
                <div className="text-[10px] text-slate-400 self-start sm:self-auto shrink-0">{new Date(log.timestamp).toLocaleString()}</div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* CREATE CUSTOM FIELD MODAL */}
      {isFieldModalOpen && (
        <ModalShell
          isOpen={isFieldModalOpen}
          onClose={() => setIsFieldModalOpen(false)}
          size="md"
          title={
            <h3 className="font-bold text-slate-900 text-sm sm:text-base flex items-center gap-2">
              <Sliders className="w-5 h-5 text-blue-600 shrink-0" />
              <span>Create Custom Field</span>
            </h3>
          }
        >
          <form onSubmit={handleCreateCustomField} className="space-y-4 text-xs">
            <div className="space-y-1">
              <Label className="font-semibold text-slate-700">Target Entity</Label>
              <CustomSelect
                value={fieldEntityType}
                onChange={setFieldEntityType}
                options={[
                  { value: 'Lead', label: 'Lead' },
                  { value: 'Contact', label: 'Contact' },
                  { value: 'Deal', label: 'Deal' },
                  { value: 'Company', label: 'Company' },
                ]}
              />
            </div>

            <div className="space-y-1">
              <Label className="font-semibold text-slate-700">Display Label</Label>
              <Input
                type="text"
                placeholder="e.g. Revenue Bracket"
                value={fieldLabel}
                onChange={(e) => setFieldLabel(e.target.value)}
                className="h-9 text-xs"
              />
            </div>

            <div className="space-y-1">
              <Label className="font-semibold text-slate-700">Field Key (API Name)</Label>
              <Input
                type="text"
                placeholder="e.g. annual_revenue_bracket"
                value={fieldName}
                onChange={(e) => setFieldName(e.target.value)}
                className="h-9 text-xs font-mono"
              />
            </div>

            <div className="space-y-1">
              <Label className="font-semibold text-slate-700">Data Type</Label>
              <CustomSelect
                value={fieldType}
                onChange={setFieldType}
                options={[
                  { value: 'text', label: 'Text String' },
                  { value: 'number', label: 'Number' },
                  { value: 'select', label: 'Dropdown Select' },
                  { value: 'boolean', label: 'Boolean Checkbox' },
                ]}
              />
            </div>

            {fieldType === 'select' && (
              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Dropdown Options</Label>
                <Input
                  type="text"
                  placeholder="Enter comma-separated options"
                  value={fieldOptions}
                  onChange={(e) => setFieldOptions(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>
            )}

            <div className="flex flex-col-reverse sm:flex-row justify-end gap-2 pt-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setIsFieldModalOpen(false)} className="w-full sm:w-auto cursor-pointer">
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={createCustomFieldMutation.isPending} className="bg-blue-600 hover:bg-blue-700 text-white font-semibold w-full sm:w-auto cursor-pointer">
                {createCustomFieldMutation.isPending ? 'Creating...' : 'Create Field'}
              </Button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* CREATE WEBHOOK MODAL */}
      {isWebhookModalOpen && (
        <ModalShell
          isOpen={isWebhookModalOpen}
          onClose={() => setIsWebhookModalOpen(false)}
          size="md"
          title={
            <h3 className="font-bold text-slate-900 text-sm sm:text-base flex items-center gap-2">
              <WebhookIcon className="w-5 h-5 text-blue-600 shrink-0" />
              <span>Register Outgoing Webhook</span>
            </h3>
          }
        >
          <form onSubmit={handleCreateWebhook} className="space-y-4 text-xs">
            <div className="space-y-1">
              <Label className="font-semibold text-slate-700">Target Webhook Endpoint URL</Label>
              <Input
                type="url"
                placeholder="https://hooks.zapier.com/hooks/catch/..."
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                className="h-9 text-xs font-mono"
              />
            </div>

            <div className="space-y-1">
              <Label className="font-semibold text-slate-700">Subscribed Events (Comma-separated)</Label>
              <Input
                type="text"
                placeholder="lead.created, deal.won, contact.updated"
                value={webhookEvents}
                onChange={(e) => setWebhookEvents(e.target.value)}
                className="h-9 text-xs font-mono"
              />
            </div>

            <div className="flex flex-col-reverse sm:flex-row justify-end gap-2 pt-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setIsWebhookModalOpen(false)} className="w-full sm:w-auto cursor-pointer">
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={createWebhookMutation.isPending} className="bg-blue-600 hover:bg-blue-700 text-white font-semibold w-full sm:w-auto cursor-pointer">
                {createWebhookMutation.isPending ? 'Registering...' : 'Register Webhook'}
              </Button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* CREATE SLA MODAL */}
      {isSlaModalOpen && (
        <ModalShell
          isOpen={isSlaModalOpen}
          onClose={() => setIsSlaModalOpen(false)}
          size="md"
          title={
            <h3 className="font-bold text-slate-900 text-sm sm:text-base flex items-center gap-2">
              <Clock className="w-5 h-5 text-blue-600 shrink-0" />
              <span>Create SLA Policy</span>
            </h3>
          }
        >
          <form onSubmit={handleCreateSla} className="space-y-4 text-xs">
            <div className="space-y-1">
              <Label className="font-semibold text-slate-700">Policy Name</Label>
              <Input
                type="text"
                placeholder="e.g. High Priority Response SLA"
                value={slaName}
                onChange={(e) => setSlaName(e.target.value)}
                className="h-9 text-xs"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Response Target (Hours)</Label>
                <Input
                  type="number"
                  value={slaResponseTime}
                  onChange={(e) => setSlaResponseTime(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>
              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Resolution Target (Hours)</Label>
                <Input
                  type="number"
                  value={slaResolutionTime}
                  onChange={(e) => setSlaResolutionTime(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>
            </div>

            <div className="flex flex-col-reverse sm:flex-row justify-end gap-2 pt-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setIsSlaModalOpen(false)} className="w-full sm:w-auto cursor-pointer">
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={createSlaMutation.isPending} className="bg-blue-600 hover:bg-blue-700 text-white font-semibold w-full sm:w-auto cursor-pointer">
                {createSlaMutation.isPending ? 'Creating...' : 'Create SLA Policy'}
              </Button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* CONFIRM DELETE ITEM MODAL */}
      <ConfirmModal
        isOpen={!!itemToDelete}
        onClose={() => setItemToDelete(null)}
        onConfirm={handleConfirmDeleteItem}
        title="Delete Item Confirmation"
        description="This action cannot be undone."
        confirmText="Delete"
        variant="danger"
        isLoading={deleteCustomFieldMutation.isPending || deleteWebhookMutation.isPending}
        message={
          itemToDelete && (
            <p>
              Are you sure you want to delete <strong className="text-slate-900">{itemToDelete.name}</strong>?
            </p>
          )
        }
      />

      {/* CONFIRM RESET DATABASE MODAL */}
      <ConfirmModal
        isOpen={isResetDbModalOpen}
        onClose={() => setIsResetDbModalOpen(false)}
        onConfirm={handleConfirmResetDb}
        title="Reset Entire Database"
        description="CRITICAL ACTION: All 70 database tables will be truncated."
        confirmText="Reset Database Now"
        variant="danger"
        isLoading={resetDatabaseMutation.isPending}
        message={
          <p>
            Are you sure you want to execute a full factory database reset? All data will be permanently cleared (protected superadmin user preserved).
          </p>
        }
      />
    </div>
  );
}
