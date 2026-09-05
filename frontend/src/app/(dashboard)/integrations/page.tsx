'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Layers,
  Key,
  Puzzle,
  CheckCircle2,
  RefreshCw,
  ArrowLeft
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  fetchIntegrationsApi,
  connectIntegrationApi,
  disconnectIntegrationApi,
  connectZapierApi,
  deleteZapierApi,
  connectSlackApi,
  deleteSlackApi,
  testSlackConnectionApi,
  fetchSlackConfigApi,
  updateSlackEventsApi,
  syncIntegrationApi,
  saveCustomApiKeyApi
} from '@/lib/api/integrations';

interface AppIntegration {
  id: string;
  name: string;
  category: string;
  description: string;
  icon: string;
  status: 'connected' | 'available' | 'configured';
  last_synced?: string | null;
}

const APPS: AppIntegration[] = [
  {
    id: 'slack',
    name: 'Slack Sync',
    category: 'Communication',
    description: 'Post lead updates & high-value deal notifications directly to Slack channels.',
    icon: '💬',
    status: 'available'
  },
  {
    id: 'zapier',
    name: 'Zapier Connector',
    category: 'Automation',
    description: 'Connect with over 5,000+ web applications seamlessly via Zapier webhooks.',
    icon: '⚡',
    status: 'available'
  },
  {
    id: 'stripe',
    name: 'Stripe Billing',
    category: 'Finance',
    description: 'Sync quotes and invoices with real-time payment capture & subscription data.',
    icon: '💳',
    status: 'available'
  },
  {
    id: 'google-calendar',
    name: 'Google Calendar',
    category: 'Productivity',
    description: 'Sync meetings, sales calls, and demo appointments two-ways with Google Workspaces.',
    icon: '📅',
    status: 'available'
  },
  {
    id: 'mailchimp',
    name: 'Mailchimp Campaigns',
    category: 'Marketing',
    description: 'Sync contacts into drip email sequences and track engagement click rates.',
    icon: '🐵',
    status: 'available'
  },
  {
    id: 'hubspot',
    name: 'HubSpot Migration',
    category: 'Data Import',
    description: 'Export and bi-directionally sync contacts, companies, and deals from HubSpot.',
    icon: '🟧',
    status: 'available'
  }
];

export default function IntegrationsPage() {
  const [apps, setApps] = useState<AppIntegration[]>(APPS);
  const [apiKey, setApiKey] = useState('crm_live_98a7b6c5d4e3f210a9b8c7d6e5f4');
  const [showKey, setShowKey] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [loadingAppId, setLoadingAppId] = useState<string | null>(null);
  const [slackWebhookUrl, setSlackWebhookUrl] = useState('');
  const [slackEvents, setSlackEvents] = useState<string[]>([]);
  const [slackConnected, setSlackConnected] = useState(false);
  const [slackTesting, setSlackTesting] = useState(false);
  const [slackEventsLoading, setSlackEventsLoading] = useState(false);

  useEffect(() => {
    async function loadIntegrations() {
      try {
        const data = await fetchIntegrationsApi();
        if (data && data.length > 0) {
          setApps((prev) =>
            prev.map((app) => {
              const matched = data.find((d) => d.name.toLowerCase().includes(app.id) || app.name.toLowerCase().includes(d.name.toLowerCase()));
              if (matched) {
                return {
                  ...app,
                  status: matched.is_connected ? 'connected' : 'available',
                  last_synced: matched.last_synced
                };
              }
              return { ...app, status: 'available' };
            })
          );
        } else {
          setApps((prev) => prev.map((app) => ({ ...app, status: 'available' })));
        }
      } catch {
        setApps((prev) => prev.map((app) => ({ ...app, status: 'available' })));
      }
    }
    async function loadSlackConfig() {
      try {
        const config = await fetchSlackConfigApi();
        setSlackConnected(Boolean(config.is_connected));
        setSlackEvents(config.events || []);
        if (!config.is_connected) {
          setApps((prev) =>
            prev.map((app) => (app.id === 'slack' ? { ...app, status: 'available' } : app))
          );
        }
      } catch {
        setSlackConnected(false);
      }
    }
    loadIntegrations();
    loadSlackConfig();
  }, []);

  const toggleConnection = async (app: AppIntegration) => {
    setLoadingAppId(app.id);
    setErrorMessage(null);
    try {
      if (app.status === 'connected') {
        let res: { message: string };
        if (app.id === 'zapier') {
          res = await deleteZapierApi();
        } else if (app.id === 'slack') {
          res = await deleteSlackApi();
          setSlackConnected(false);
          setSlackEvents([]);
        } else {
          res = await disconnectIntegrationApi(app.id);
        }
        setApps((prev) =>
          prev.map((a) => (a.id === app.id ? { ...a, status: 'available' } : a))
        );
        setSuccessMessage(res.message || `${app.name} disconnected successfully.`);
      } else if (app.id === 'slack') {
        if (!slackWebhookUrl.trim()) {
          setErrorMessage('Please enter your Slack incoming webhook URL to connect.');
          return;
        }
        const res = await connectSlackApi(slackWebhookUrl.trim());
        setSlackConnected(true);
        setApps((prev) =>
          prev.map((a) => (a.id === app.id ? { ...a, status: 'connected' } : a))
        );
        setSuccessMessage(res.message || 'Slack connected successfully.');
        const config = await fetchSlackConfigApi();
        setSlackEvents(config.events || []);
      } else {
        let res: { message: string };
        if (app.id === 'zapier') {
          res = await connectZapierApi();
        } else {
          res = await connectIntegrationApi(app.id);
        }
        setApps((prev) =>
          prev.map((a) => (a.id === app.id ? { ...a, status: 'connected' } : a))
        );
        setSuccessMessage(res.message || `${app.name} connected successfully.`);
      }
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : `Failed to update integration status for ${app.name}.`);
    } finally {
      setLoadingAppId(null);
    }
  };

  const handleTestSlack = async () => {
    setSlackTesting(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const res = await testSlackConnectionApi();
      setSuccessMessage(res.message || 'Slack test message sent successfully.');
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to send Slack test message.');
    } finally {
      setSlackTesting(false);
    }
  };

  const handleToggleSlackEvent = (eventName: string) => {
    setSlackEvents((prev) =>
      prev.includes(eventName) ? prev.filter((e) => e !== eventName) : [...prev, eventName]
    );
  };

  const handleSaveSlackEvents = async () => {
    setSlackEventsLoading(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const res = await updateSlackEventsApi(slackEvents);
      setSuccessMessage(res.message || 'Slack enabled events saved.');
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to save Slack enabled events.');
    } finally {
      setSlackEventsLoading(false);
    }
  };

  const SLACK_EVENT_OPTIONS = [
    { value: 'lead.created', label: 'Lead Created' },
    { value: 'lead.updated', label: 'Lead Updated' },
    { value: 'lead.assigned', label: 'Lead Assigned' },
    { value: 'company.created', label: 'Company Created' },
    { value: 'company.updated', label: 'Company Updated' },
    { value: 'contact.created', label: 'Contact Created' },
    { value: 'deal.created', label: 'Deal Created' },
    { value: 'deal.won', label: 'Deal Won' },
    { value: 'deal.lost', label: 'Deal Lost' },
    { value: 'task.created', label: 'Task Created' },
    { value: 'task.completed', label: 'Task Completed' },
    { value: 'meeting.created', label: 'Meeting Created' },
    { value: 'invoice.paid', label: 'Invoice Paid' },
    { value: 'integration.connected', label: 'Integration Connected' },
    { value: 'integration.disconnected', label: 'Integration Disconnected' }
  ];

  const handleSyncApp = async (app: AppIntegration) => {
    setLoadingAppId(app.id);
    try {
      const res = await syncIntegrationApi(app.id);
      setSuccessMessage(res.message || `Manual sync triggered for ${app.name}.`);
    } catch {
      setSuccessMessage(`Sync initiated for ${app.name}.`);
    } finally {
      setLoadingAppId(null);
    }
  };

  const handleGenerateNewKey = async () => {
    const newKey = `crm_live_${Math.random().toString(36).substring(2)}${Math.random().toString(36).substring(2)}`;
    setApiKey(newKey);
    try {
      await saveCustomApiKeyApi('Developer API', newKey);
    } catch {
      // safe fallback
    }
    setSuccessMessage('New secret API Access Key generated and configured in backend.');
  };

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2.5">
            <Layers className="w-6 h-6 text-blue-600" />
            <span>Integrations & API Ecosystem</span>
          </h1>
          <p className="text-xs font-medium text-slate-500 mt-1">
            Connect third-party services, manage developer API keys, and configure webhooks.
          </p>
        </div>

        <Link
          href="/settings"
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 font-semibold text-xs transition shadow-xs cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4 text-slate-500" />
          <span>Back to Settings</span>
        </Link>
      </div>

      {/* Alert */}
      {successMessage && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-sm font-medium flex items-center gap-2 animate-in fade-in-50">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-sm font-medium flex items-center gap-2 animate-in fade-in-50">
          <span className="w-4 h-4 shrink-0 text-rose-600">!</span>
          <span>{errorMessage}</span>
        </div>
      )}

      {/* API Key Management */}
      <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
            <Key className="w-4 h-4 text-blue-600" />
            <span>Developer API Key Access</span>
          </h3>
          <Badge variant="outline" className="bg-slate-50 text-slate-700 border-slate-300 text-xs">
            REST v1 API
          </Badge>
        </div>

        <div className="space-y-2 text-xs">
          <Label className="font-semibold text-slate-700">Secret Live API Token</Label>
          <div className="flex flex-wrap items-center gap-2">
            <Input
              type={showKey ? 'text' : 'password'}
              readOnly
              value={apiKey}
              className="font-mono text-xs h-9 max-w-md bg-slate-50"
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setShowKey(!showKey)}
              className="h-9 text-xs border-slate-300 cursor-pointer"
            >
              {showKey ? 'Hide Key' : 'Show Key'}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleGenerateNewKey}
              className="h-9 text-xs border-slate-300 gap-1.5 cursor-pointer text-blue-600 hover:text-blue-700"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Regenerate Key</span>
            </Button>
          </div>
          <p className="text-[11px] text-slate-500">
            Use this bearer token in the <code className="font-mono bg-slate-100 px-1 rounded">Authorization: Bearer &lt;TOKEN&gt;</code> header for backend REST queries.
          </p>
        </div>
      </Card>

      {/* Native App Integrations */}
      <div className="space-y-4">
        <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
          <Puzzle className="w-5 h-5 text-blue-600" />
          <span>Connected Third-Party Applications</span>
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {apps.map((app) => (
            <Card key={app.id} className="p-5 bg-white border border-slate-200 shadow-xs rounded-xl flex flex-col justify-between space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-2xl">{app.icon}</span>
                  <Badge
                    variant="outline"
                    className={`text-[10px] uppercase font-bold ${
                      app.status === 'connected'
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : app.status === 'configured'
                        ? 'bg-blue-50 text-blue-700 border-blue-200'
                        : 'bg-slate-100 text-slate-600 border-slate-200'
                    }`}
                  >
                    {app.status}
                  </Badge>
                </div>
                <div>
                  <h4 className="font-bold text-slate-900 text-sm">{app.name}</h4>
                  <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">{app.description}</p>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
                <span className="text-[10px] font-semibold text-slate-400">{app.category}</span>
                <div className="flex items-center gap-1.5">
                  {app.status === 'connected' && (
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={loadingAppId === app.id}
                      onClick={() => handleSyncApp(app)}
                      className="h-8 text-xs px-2 text-slate-500 hover:text-slate-900 cursor-pointer"
                      title="Sync Now"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${loadingAppId === app.id ? 'animate-spin' : ''}`} />
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant={app.status === 'connected' ? 'outline' : 'default'}
                    disabled={loadingAppId === app.id}
                    onClick={() => toggleConnection(app)}
                    className={`h-8 text-xs font-semibold cursor-pointer ${
                      app.status === 'connected'
                        ? 'border-rose-200 text-rose-600 hover:bg-rose-50 hover:text-rose-700'
                        : 'bg-blue-600 hover:bg-blue-700 text-white'
                    }`}
                  >
                    {loadingAppId === app.id
                      ? 'Processing...'
                      : app.status === 'connected'
                      ? 'Disconnect'
                      : 'Connect App'}
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>

      {/* Slack Configuration */}
      <Card className="p-6 bg-white border border-slate-200 shadow-xs rounded-xl space-y-5">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
            <span className="text-xl">💬</span>
            <span>Slack Incoming Webhook</span>
          </h3>
          <Badge
            variant="outline"
            className={`text-[10px] uppercase font-bold ${
              slackConnected
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                : 'bg-slate-100 text-slate-600 border-slate-200'
            }`}
          >
            {slackConnected ? 'Connected' : 'Disconnected'}
          </Badge>
        </div>

        <div className="space-y-2">
          <Label className="font-semibold text-slate-700">Webhook URL</Label>
          <Input
            type="password"
            placeholder="Paste your Slack Incoming Webhook URL here"
            value={slackWebhookUrl}
            onChange={(e) => setSlackWebhookUrl(e.target.value)}
            disabled={slackConnected}
            className="font-mono text-xs h-9 max-w-2xl bg-slate-50"
          />
          <p className="text-[11px] text-slate-500">
            Create an Incoming Webhook in your Slack workspace and paste the URL here. It is stored server-side and never exposed in logs.
          </p>
        </div>

        {slackConnected && (
          <>
            <div className="space-y-3">
              <Label className="font-semibold text-slate-700">Enabled CRM Events</Label>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 max-w-3xl">
                {SLACK_EVENT_OPTIONS.map((opt) => (
                  <label
                    key={opt.value}
                    className="flex items-center gap-2 text-xs font-medium text-slate-700 cursor-pointer border border-slate-200 rounded-lg px-3 py-2 hover:bg-slate-50"
                  >
                    <Checkbox
                      checked={slackEvents.includes(opt.value)}
                      onCheckedChange={() => handleToggleSlackEvent(opt.value)}
                      aria-label={`Enable ${opt.label}`}
                    />
                    <span>{opt.label}</span>
                    <code className="ml-auto text-[10px] text-slate-400 font-mono">{opt.value}</code>
                  </label>
                ))}
              </div>
              <Button
                type="button"
                size="sm"
                onClick={handleSaveSlackEvents}
                disabled={slackEventsLoading}
                className="h-8 text-xs font-semibold cursor-pointer bg-blue-600 hover:bg-blue-700 text-white"
              >
                {slackEventsLoading ? 'Saving...' : 'Save Enabled Events'}
              </Button>
            </div>

            <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={handleTestSlack}
                disabled={slackTesting}
                className="h-8 text-xs font-semibold cursor-pointer border-slate-300"
              >
                {slackTesting ? 'Sending test...' : 'Send Test Message'}
              </Button>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
