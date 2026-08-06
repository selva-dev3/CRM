'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  Layers,
  Webhook,
  Key,
  Puzzle,
  CheckCircle2,
  AlertCircle,
  Plus,
  RefreshCw,
  Zap,
  ExternalLink,
  ShieldCheck,
  ArrowLeft
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';

interface AppIntegration {
  id: string;
  name: string;
  category: string;
  description: string;
  icon: string;
  status: 'connected' | 'available' | 'configured';
}

const APPS: AppIntegration[] = [
  {
    id: 'slack',
    name: 'Slack Sync',
    category: 'Communication',
    description: 'Post lead updates & high-value deal notifications directly to Slack channels.',
    icon: '💬',
    status: 'connected'
  },
  {
    id: 'zapier',
    name: 'Zapier Connector',
    category: 'Automation',
    description: 'Connect with over 5,000+ web applications seamlessly via Zapier webhooks.',
    icon: '⚡',
    status: 'connected'
  },
  {
    id: 'stripe',
    name: 'Stripe Billing',
    category: 'Finance',
    description: 'Sync quotes and invoices with real-time payment capture & subscription data.',
    icon: '💳',
    status: 'configured'
  },
  {
    id: 'google-calendar',
    name: 'Google Calendar',
    category: 'Productivity',
    description: 'Sync meetings, sales calls, and demo appointments two-ways with Google Workspaces.',
    icon: '📅',
    status: 'connected'
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

  const toggleConnection = (id: string) => {
    setApps((prev) =>
      prev.map((app) => {
        if (app.id === id) {
          const nextStatus = app.status === 'connected' ? 'available' : 'connected';
          setSuccessMessage(`${app.name} is now ${nextStatus === 'connected' ? 'connected' : 'disconnected'}.`);
          return { ...app, status: nextStatus };
        }
        return app;
      })
    );
  };

  const handleGenerateNewKey = () => {
    const newKey = `crm_live_${Math.random().toString(36).substring(2)}${Math.random().toString(36).substring(2)}`;
    setApiKey(newKey);
    setSuccessMessage('New secret API Access Key generated successfully.');
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
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-sm font-medium flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{successMessage}</span>
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
          <div className="flex items-center gap-2">
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
                <Button
                  size="sm"
                  variant={app.status === 'connected' ? 'outline' : 'default'}
                  onClick={() => toggleConnection(app.id)}
                  className={`h-8 text-xs font-semibold cursor-pointer ${
                    app.status === 'connected'
                      ? 'border-rose-200 text-rose-600 hover:bg-rose-50 hover:text-rose-700'
                      : 'bg-blue-600 hover:bg-blue-700 text-white'
                  }`}
                >
                  {app.status === 'connected' ? 'Disconnect' : 'Connect App'}
                </Button>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
