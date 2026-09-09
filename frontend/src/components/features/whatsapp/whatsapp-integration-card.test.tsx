import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  permissions: new Set<string>(),
  status: vi.fn(),
  configure: vi.fn(),
  action: vi.fn(),
}));

vi.mock('@/hooks/use-has-permission', () => ({
  useHasPermission: () => ({ hasPermission: (permission: string) => mocks.permissions.has(permission) }),
}));

vi.mock('@/lib/api/whatsapp', () => ({
  useWhatsAppStatus: (...args: unknown[]) => mocks.status(...args),
  useWhatsAppConfiguration: () => ({
    configure: mocks.configure,
    action: { mutateAsync: mocks.action, isPending: false },
  }),
}));

vi.mock('@/components/common/user-select', () => ({
  UserSelect: ({ value, onChange }: { value: string; onChange: (value: string) => void }) => (
    <select aria-label="User selection" value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">None</option><option value="user-a">Agent A</option>
    </select>
  ),
}));

import { PERMISSIONS } from '@/lib/permissions';
import { WhatsAppIntegrationCard } from './whatsapp-integration-card';

const connected = {
  configured: true,
  enabled: true,
  phone_index_ready: true,
  status: 'connected',
  business_account_id: '1001',
  phone_number_id: '2002',
  display_phone_number: '+14155552671',
  verified_name: 'Example Business',
  api_version: 'v23.0',
  default_phone_region: 'US',
  last_webhook_at: null,
  last_successful_message_at: null,
  ai_user_id: 'user-a',
  default_assignee_id: 'user-a',
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.permissions.clear();
  mocks.status.mockReturnValue({ data: connected, isLoading: false, isError: false });
  mocks.configure.mockResolvedValue(connected);
  mocks.action.mockResolvedValue({});
});

describe('WhatsAppIntegrationCard', () => {
  it('renders safe connection metadata but no credential form without manage permission', () => {
    mocks.permissions.add(PERMISSIONS.INTEGRATIONS.READ);
    render(<WhatsAppIntegrationCard />);

    expect(screen.getByText('Connected')).toBeInTheDocument();
    expect(screen.getByText('+14155552671')).toBeInTheDocument();
    expect(screen.queryByLabelText('Access token')).not.toBeInTheDocument();
  });

  it('submits credentials as write-only data and supports operational actions', async () => {
    mocks.permissions.add(PERMISSIONS.INTEGRATIONS.MANAGE);
    const user = userEvent.setup();
    render(<WhatsAppIntegrationCard />);

    fireEvent.change(screen.getByLabelText('Access token'), { target: { value: 'synthetic-access-token-value' } });
    await user.click(screen.getByRole('button', { name: 'Save credentials' }));
    expect(mocks.configure).toHaveBeenCalledWith(expect.objectContaining({
      business_account_id: '1001',
      phone_number_id: '2002',
      access_token: 'synthetic-access-token-value',
      default_assignee_id: 'user-a',
    }));

    await user.click(screen.getByRole('button', { name: 'Verify' }));
    await user.click(screen.getByRole('button', { name: 'Sync templates' }));
    expect(mocks.action).toHaveBeenCalledWith('verify');
    expect(mocks.action).toHaveBeenCalledWith('sync-templates');
  });

  it('shows loading and error states', () => {
    mocks.status.mockReturnValue({ data: undefined, isLoading: true, isError: false });
    const { rerender } = render(<WhatsAppIntegrationCard />);
    expect(screen.getByLabelText('Loading WhatsApp connection')).toBeInTheDocument();

    mocks.status.mockReturnValue({ data: undefined, isLoading: false, isError: true, error: new Error('Connection unavailable') });
    rerender(<WhatsAppIntegrationCard />);
    expect(screen.getByRole('alert')).toHaveTextContent('Connection unavailable');
  });
});
