import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const logLeadCallApi = vi.fn();
const updateLeadCallApi = vi.fn();
const deleteLeadCallApi = vi.fn();

vi.mock('@/lib/api/leads', () => ({
  logLeadCallApi: (...args: unknown[]) => logLeadCallApi(...args),
  updateLeadCallApi: (...args: unknown[]) => updateLeadCallApi(...args),
  deleteLeadCallApi: (...args: unknown[]) => deleteLeadCallApi(...args),
}));

vi.mock('@/components/common/responsive-select', () => ({
  ResponsiveSelect: ({
    id,
    value,
    onValueChange,
    children,
  }: {
    id: string;
    value: string;
    onValueChange: (value: string) => void;
    children: ReactNode;
  }) => <select id={id} value={value} onChange={(event) => onValueChange(event.target.value)}>{children}</select>,
}));

import { LeadCallLogSection } from './lead-call-log-section';

function renderSection(permissions: string[], calls: React.ComponentProps<typeof LeadCallLogSection>['calls'] = []) {
  window.localStorage.setItem('user', JSON.stringify({ permissions }));
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(queryClient, 'invalidateQueries');
  render(
    <QueryClientProvider client={queryClient}>
      <LeadCallLogSection
        leadId="lead-1"
        leadContactName="Jane Doe"
        relatedContactId="contact-1"
        calls={calls}
        isLoading={false}
        isError={false}
        onRetry={vi.fn()}
        timeZone="UTC"
      />
    </QueryClientProvider>,
  );
  return { invalidate };
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  logLeadCallApi.mockResolvedValue({ id: 'call-1' });
  updateLeadCallApi.mockResolvedValue({ id: 'call-1' });
  deleteLeadCallApi.mockResolvedValue({ message: 'Deleted', status: 'success' });
});

describe('LeadCallLogSection', () => {
  const existingCall = {
    id: 'call-1',
    call_type: 'Outbound' as const,
    disposition: 'Completed' as const,
    duration_seconds: 60,
    subject: 'Discovery call',
    notes: 'Initial notes',
    timestamp: '2026-09-08T10:00:00Z',
  };

  it('hides create, edit, and delete controls without their permissions', () => {
    renderSection(['calls:read'], [{
      id: 'call-1',
      call_type: 'Outbound',
      disposition: 'Completed',
      duration_seconds: 60,
      timestamp: '2026-09-08T10:00:00Z',
    }]);

    expect(screen.queryByRole('button', { name: 'Log Call' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Edit/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Delete/ })).not.toBeInTheDocument();
  });

  it('rejects a negative duration before sending the request', async () => {
    const user = userEvent.setup();
    renderSection(['calls:read', 'calls:create']);
    await user.click(screen.getByRole('button', { name: 'Log Call' }));
    const dialog = screen.getByRole('dialog', { name: 'Log phone call' });
    const duration = within(dialog).getByLabelText('Duration (seconds) *');
    await user.clear(duration);
    await user.type(duration, '-1');
    await user.click(within(dialog).getByRole('button', { name: 'Log Call' }));

    expect(await within(dialog).findByText('Duration cannot be negative.')).toBeVisible();
    expect(logLeadCallApi).not.toHaveBeenCalled();
  });

  it('focuses the shared picker when a required follow-up date is missing', async () => {
    const user = userEvent.setup();
    renderSection(['calls:read', 'calls:create']);
    await user.click(screen.getByRole('button', { name: 'Log Call' }));
    const dialog = screen.getByRole('dialog', { name: 'Log phone call' });
    await user.click(within(dialog).getByLabelText('Follow-up required'));
    const followUpPicker = within(dialog).getByLabelText('Follow-up Date / Time *');

    await user.click(within(dialog).getByRole('button', { name: 'Log Call' }));

    expect(await within(dialog).findByText('Follow-up date and time are required.')).toBeVisible();
    await waitFor(() => expect(followUpPicker).toHaveFocus());
    expect(logLeadCallApi).not.toHaveBeenCalled();
  });

  it('creates once with an idempotency key and refreshes calls and timeline', async () => {
    const user = userEvent.setup();
    const { invalidate } = renderSection(['calls:read', 'calls:create']);
    await user.click(screen.getByRole('button', { name: 'Log Call' }));
    const dialog = screen.getByRole('dialog', { name: 'Log phone call' });
    await user.type(within(dialog).getByLabelText('Subject / Title'), 'Discovery call');
    await user.click(within(dialog).getByRole('button', { name: 'Log Call' }));

    await waitFor(() => expect(logLeadCallApi).toHaveBeenCalledTimes(1));
    expect(logLeadCallApi).toHaveBeenCalledWith(
      'lead-1',
      expect.objectContaining({
        contact_id: 'contact-1',
        subject: 'Discovery call',
        call_type: 'Outbound',
        disposition: 'Completed',
        duration_seconds: 0,
      }),
      expect.any(String),
    );
    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['lead-calls', 'lead-1'] });
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['lead-timeline', 'lead-1'] });
    });
  });

  it('updates an existing call without rewriting its relationships', async () => {
    const user = userEvent.setup();
    const { invalidate } = renderSection(['calls:read', 'calls:update'], [existingCall]);

    await user.click(screen.getByRole('button', { name: 'Edit Discovery call' }));
    const dialog = screen.getByRole('dialog', { name: 'Edit call log' });
    const notes = within(dialog).getByLabelText('Notes / Conversation Summary');
    await user.clear(notes);
    await user.type(notes, 'Updated notes');
    await user.click(within(dialog).getByRole('button', { name: 'Save Changes' }));

    await waitFor(() => expect(updateLeadCallApi).toHaveBeenCalledTimes(1));
    expect(updateLeadCallApi).toHaveBeenCalledWith(
      'call-1',
      expect.objectContaining({ notes: 'Updated notes' }),
    );
    expect(updateLeadCallApi.mock.calls[0][1]).not.toHaveProperty('lead_id');
    expect(updateLeadCallApi.mock.calls[0][1]).not.toHaveProperty('contact_id');
    expect(updateLeadCallApi.mock.calls[0][1]).not.toHaveProperty('company_id');
    expect(updateLeadCallApi.mock.calls[0][1]).not.toHaveProperty('deal_id');
    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['lead-calls', 'lead-1'] });
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['lead-timeline', 'lead-1'] });
    });
  });

  it('confirms deletion and refreshes the calls count and timeline', async () => {
    const user = userEvent.setup();
    const { invalidate } = renderSection(['calls:read', 'calls:delete'], [existingCall]);

    await user.click(screen.getByRole('button', { name: 'Delete Discovery call' }));
    const dialog = screen.getByRole('dialog', { name: 'Delete call log' });
    expect(deleteLeadCallApi).not.toHaveBeenCalled();
    await user.click(within(dialog).getByRole('button', { name: 'Delete' }));

    await waitFor(() => expect(deleteLeadCallApi).toHaveBeenCalledWith('call-1'));
    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['lead-calls', 'lead-1'] });
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['lead-timeline', 'lead-1'] });
    });
  });

  it('keeps the form open and displays an API error', async () => {
    logLeadCallApi.mockRejectedValue(new Error('Call could not be saved'));
    const user = userEvent.setup();
    renderSection(['calls:read', 'calls:create']);

    await user.click(screen.getByRole('button', { name: 'Log Call' }));
    const dialog = screen.getByRole('dialog', { name: 'Log phone call' });
    await user.type(within(dialog).getByLabelText('Subject / Title'), 'Retry-safe call');
    await user.click(within(dialog).getByRole('button', { name: 'Log Call' }));

    expect(await within(dialog).findByText('Call could not be saved')).toBeVisible();
    expect(dialog).toBeVisible();
    expect(within(dialog).getByLabelText('Subject / Title')).toHaveValue('Retry-safe call');
  });

  it('does not carry a form error into a later delete confirmation', async () => {
    logLeadCallApi.mockRejectedValue(new Error('Call could not be saved'));
    const user = userEvent.setup();
    renderSection(['calls:read', 'calls:create', 'calls:delete'], [existingCall]);

    await user.click(screen.getByRole('button', { name: 'Log Call' }));
    const formDialog = screen.getByRole('dialog', { name: 'Log phone call' });
    await user.click(within(formDialog).getByRole('button', { name: 'Log Call' }));
    expect(await within(formDialog).findByText('Call could not be saved')).toBeVisible();
    await user.click(within(formDialog).getByRole('button', { name: 'Cancel' }));

    await user.click(screen.getByRole('button', { name: 'Delete Discovery call' }));
    const deleteDialog = screen.getByRole('dialog', { name: 'Delete call log' });
    expect(within(deleteDialog).queryByText('Call could not be saved')).not.toBeInTheDocument();
  });
});
