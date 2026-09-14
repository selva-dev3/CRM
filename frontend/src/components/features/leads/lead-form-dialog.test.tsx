import type { ReactNode } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  create: vi.fn(),
  update: vi.fn(),
  canAssign: true,
  duplicate: null as null | { is_duplicate: boolean; matched_lead_id: string | null },
  customFields: [] as Array<{ field_name: string; field_type: 'text'; label: string; options: string[] }>,
}));

vi.mock('@tanstack/react-query', () => ({
  useQuery: ({ queryKey }: { queryKey: readonly unknown[] }) => queryKey[0] === 'companies'
    ? { data: [{ id: 'company-1', name: 'Acme' }], isFetching: false }
    : { data: mocks.duplicate, isFetching: false },
}));

vi.mock('@/hooks/use-has-permission', () => ({
  useHasPermission: () => ({ hasPermission: () => mocks.canAssign }),
}));

vi.mock('@/lib/api/leads', () => ({
  checkLeadDuplicateApi: vi.fn(),
  useCreateLeadMutation: () => ({ mutateAsync: mocks.create, isPending: false }),
  useUpdateLeadMutation: () => ({ mutateAsync: mocks.update, isPending: false }),
}));

vi.mock('@/lib/api/companies', () => ({
  companyKeys: { list: () => ['companies'] },
  fetchCompaniesApi: vi.fn(),
}));

vi.mock('@/lib/api/organizations', () => ({
  useCurrentOrganizationQuery: () => ({ data: { id: 'org-1', name: 'Northwind' }, isLoading: false }),
}));

vi.mock('@/lib/api/custom-fields', () => ({
  useEntityCustomFieldsQuery: () => ({ data: mocks.customFields, isLoading: false, isError: false }),
}));

vi.mock('@/components/common/user-select', () => ({
  UserSelect: ({ onChange }: { onChange: (value: string) => void }) => (
    <button type="button" onClick={() => onChange('user-1')}>Assign lead to user</button>
  ),
}));

vi.mock('@/components/common/modal-shell', () => ({
  ModalShell: ({ children, title, onClose, ariaLabel }: { children: ReactNode; title: ReactNode; onClose: () => void; ariaLabel: string }) => (
    <div role="dialog" aria-label={ariaLabel}>
      {title}
      <button type="button" aria-label="Close dialog" onClick={onClose}>Close</button>
      {children}
    </div>
  ),
}));

vi.mock('@/components/common/confirm-modal', () => ({
  ConfirmModal: ({ isOpen, onClose, onConfirm, title, confirmText, cancelText }: { isOpen: boolean; onClose: () => void; onConfirm: () => void; title: string; confirmText: string; cancelText: string }) => isOpen ? (
    <div role="alertdialog" aria-label={title}>
      <button type="button" onClick={onClose}>{cancelText}</button>
      <button type="button" onClick={onConfirm}>{confirmText}</button>
    </div>
  ) : null,
}));

import { LeadFormDialog } from './lead-form-dialog';

const savedLead = {
  id: 'lead-1',
  title: 'Jane Doe Opportunity',
  company: 'Acme',
  contact_name: 'Jane Doe',
  email: 'jane@acme.test',
  status: 'New',
  source: 'Website',
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.canAssign = true;
  mocks.duplicate = null;
  mocks.customFields = [];
  mocks.create.mockResolvedValue(savedLead);
  mocks.update.mockResolvedValue(savedLead);
});

async function reachCompanyStep(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Contact name *'), 'Jane Doe');
  await user.type(screen.getByLabelText('Email address *'), 'jane@acme.test');
  await user.click(screen.getByRole('button', { name: 'Continue' }));
  expect(await screen.findByRole('heading', { name: 'Company and location' })).toBeVisible();
}

describe('LeadFormDialog', () => {
  it('validates the current step before advancing', async () => {
    const user = userEvent.setup();
    render(<LeadFormDialog isOpen onClose={vi.fn()} onSaved={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'Continue' }));

    expect(await screen.findByText('Contact name is required.')).toBeVisible();
    expect(screen.getByText('Email address is required.')).toBeVisible();
    expect(screen.queryByRole('heading', { name: 'Company and location' })).not.toBeInTheDocument();
  });

  it('submits a minimal lead without client-owned organization or score defaults', async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();
    render(<LeadFormDialog isOpen onClose={vi.fn()} onSaved={onSaved} />);

    await reachCompanyStep(user);
    await user.type(screen.getByLabelText('Company name *'), 'Acme');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: 'Create lead' }));

    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(1));
    expect(mocks.create).toHaveBeenCalledWith(expect.objectContaining({
      contact_name: 'Jane Doe',
      email: 'jane@acme.test',
      company: 'Acme',
      title: 'Jane Doe Opportunity',
      status: 'New',
    }));
    const payload = mocks.create.mock.calls[0][0];
    expect(payload).not.toHaveProperty('organization_id');
    expect(payload).not.toHaveProperty('score');
    expect(onSaved).toHaveBeenCalledWith(savedLead, 'created');
  });

  it('shows a non-blocking duplicate warning linked to the existing lead', () => {
    mocks.duplicate = { is_duplicate: true, matched_lead_id: 'existing-1' };
    render(<LeadFormDialog isOpen onClose={vi.fn()} onSaved={vi.fn()} />);

    expect(screen.getByText(/A lead with this email already exists/)).toBeVisible();
    expect(screen.getByRole('link', { name: 'Review existing lead' })).toHaveAttribute('href', '/leads/existing-1');
  });

  it('does not expose assignment without the lead assignment permission', async () => {
    mocks.canAssign = false;
    const user = userEvent.setup();
    render(<LeadFormDialog isOpen onClose={vi.fn()} onSaved={vi.fn()} />);

    await reachCompanyStep(user);
    await user.type(screen.getByLabelText('Company name *'), 'Acme');
    await user.click(screen.getByRole('button', { name: 'Continue' }));

    expect(screen.queryByRole('button', { name: 'Assign lead to user' })).not.toBeInTheDocument();
  });

  it('asks before closing a dirty form', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<LeadFormDialog isOpen onClose={onClose} onSaved={vi.fn()} />);

    await user.type(screen.getByLabelText('Contact name *'), 'Jane');
    await user.click(screen.getByRole('button', { name: 'Close dialog' }));
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole('alertdialog', { name: 'Discard unsaved changes?' })).toBeVisible();

    await user.click(screen.getByRole('button', { name: 'Discard changes' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('submits dotted custom-field names as literal keys when creating', async () => {
    mocks.customFields = [{ field_name: 'account.tier', field_type: 'text', label: 'Account tier', options: [] }];
    const user = userEvent.setup();
    render(<LeadFormDialog isOpen onClose={vi.fn()} onSaved={vi.fn()} />);

    await reachCompanyStep(user);
    await user.type(screen.getByLabelText('Company name *'), 'Acme');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.type(screen.getByLabelText('Account tier'), 'Gold');
    await user.click(screen.getByRole('button', { name: 'Create lead' }));

    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith(
      expect.objectContaining({ custom_fields: { 'account.tier': 'Gold' } }),
    ));
  });

  it('updates dotted custom-field names without creating nested values', async () => {
    mocks.customFields = [{ field_name: 'account.tier', field_type: 'text', label: 'Account tier', options: [] }];
    const user = userEvent.setup();
    const existingLead = { ...savedLead, custom_fields: { 'account.tier': 'Silver' } };
    render(<LeadFormDialog isOpen onClose={vi.fn()} lead={existingLead} onSaved={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    const customField = screen.getByLabelText('Account tier');
    expect(customField).toHaveValue('Silver');
    await user.clear(customField);
    await user.type(customField, 'Gold');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({
      id: 'lead-1',
      payload: expect.objectContaining({ custom_fields: { 'account.tier': 'Gold' } }),
    }));
  });
});
