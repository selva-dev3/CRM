import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';

const mutation = vi.hoisted(() => () => ({
  isPending: false,
  mutateAsync: vi.fn().mockResolvedValue({}),
}));

vi.mock('@/lib/api/settings', () => ({
  useSystemSettingsQuery: vi.fn().mockReturnValue({
    data: {
      org_name: 'Enterprise Organization',
      currency: 'USD',
      currency_symbol: '$',
      timezone: 'UTC',
      smtp_enabled: true,
      ai_enabled: true,
      smtp_host: 'smtp.example.com',
      smtp_port: 587,
      smtp_user: '',
      smtp_pass: '',
      support_email: 'support@company.com',
      reset_database: false,
      backup_frequency_days: 7,
    },
    isLoading: false,
    refetch: vi.fn(),
  }),
  useUpdateSystemSettingsMutation: mutation,
  useAuditLogsQuery: vi.fn().mockReturnValue({ data: [] }),
  exportAuditLogsCsvApi: vi.fn(),
  useCustomFieldsQuery: vi.fn().mockReturnValue({ data: [] }),
  useCreateCustomFieldMutation: mutation,
  useDeleteCustomFieldMutation: mutation,
  useWebhooksQuery: vi.fn().mockReturnValue({ data: [] }),
  useCreateWebhookMutation: mutation,
  useDeleteWebhookMutation: mutation,
  useTestWebhookMutation: mutation,
  useSlaPoliciesQuery: vi.fn().mockReturnValue({ data: [] }),
  useCreateSlaPolicyMutation: mutation,
  useBackupsQuery: vi.fn().mockReturnValue({ data: [] }),
  useTriggerBackupMutation: mutation,
  useResetDatabaseMutation: mutation,
}));

vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: { href: string; children?: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

import SettingsPage from './page';
import { PERMISSIONS } from '@/lib/permissions';

function setStoredUser(permissions: string[]): void {
  window.localStorage.setItem('user', JSON.stringify({ role: 'member', email: 'member@company.com', permissions }));
}

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
});

describe('Settings page permission gating', () => {
  it('hides the Organization Settings link without organization:read', () => {
    setStoredUser([]);
    render(<SettingsPage />);
    expect(screen.queryByRole('link', { name: /Organization Settings/ })).not.toBeInTheDocument();
  });

  it('shows the Organization Settings link with organization:read', () => {
    setStoredUser([PERMISSIONS.ORGANIZATION.READ]);
    render(<SettingsPage />);
    expect(screen.getByRole('link', { name: /Organization Settings/ })).toBeInTheDocument();
  });

  it('hides the Integrations link without integrations:read', () => {
    setStoredUser([]);
    render(<SettingsPage />);
    expect(screen.queryByRole('link', { name: /Integrations/ })).not.toBeInTheDocument();
  });

  it('shows the Integrations link with integrations:read', () => {
    setStoredUser([PERMISSIONS.INTEGRATIONS.READ]);
    render(<SettingsPage />);
    expect(screen.getByRole('link', { name: /Integrations/ })).toBeInTheDocument();
  });

  it('hides the Security Audit Trail tab without settings:security', () => {
    setStoredUser([PERMISSIONS.SETTINGS.READ]);
    render(<SettingsPage />);
    expect(screen.queryByRole('tab', { name: /Security Audit Trail/ })).not.toBeInTheDocument();
  });

  it('shows the Security Audit Trail tab with settings:security', () => {
    setStoredUser([PERMISSIONS.SETTINGS.READ, PERMISSIONS.SETTINGS.SECURITY]);
    render(<SettingsPage />);
    expect(screen.getByRole('tab', { name: /Security Audit Trail/ })).toBeInTheDocument();
  });

  it('hides write actions without settings:update', () => {
    setStoredUser([PERMISSIONS.SETTINGS.READ]);
    render(<SettingsPage />);
    expect(screen.queryByRole('button', { name: /Save General Settings/ })).not.toBeInTheDocument();
  });

  it('shows write actions with settings:update', () => {
    setStoredUser([PERMISSIONS.SETTINGS.READ, PERMISSIONS.SETTINGS.UPDATE]);
    render(<SettingsPage />);
    expect(screen.getByRole('button', { name: /Save General Settings/ })).toBeInTheDocument();
  });

  it('superadmin holding every catalog key sees every gated element', () => {
    const allKeys = Object.values(PERMISSIONS).flatMap((group) => Object.values(group));
    setStoredUser(allKeys);
    render(<SettingsPage />);
    expect(screen.getByRole('link', { name: /Organization Settings/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Integrations/ })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Security Audit Trail/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Save General Settings/ })).toBeInTheDocument();
  });
});
