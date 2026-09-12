import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const fetchLeadsApiMock = vi.fn();
const fetchContactsApiMock = vi.fn();

vi.mock('@/lib/api/leads', () => ({
  fetchLeadsApi: (...args: unknown[]) => fetchLeadsApiMock(...args),
}));
vi.mock('@/lib/api/contacts', () => ({
  fetchContactsApi: (...args: unknown[]) => fetchContactsApiMock(...args),
}));
vi.mock('@/lib/api/deals', () => ({ fetchDealsApi: vi.fn() }));
vi.mock('@/lib/api/companies', () => ({ fetchCompaniesApi: vi.fn() }));

import { EntityReferenceSelect } from './entity-reference-select';

function Wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      {children}
    </QueryClientProvider>
  );
}

describe('EntityReferenceSelect', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.setItem('user', JSON.stringify({
      permissions: ['leads:read'],
    }));
    fetchLeadsApiMock.mockResolvedValue({
      items: [{
        id: 'lead-1',
        contact_name: 'Jane Doe',
        title: 'Renewal',
        company: 'Acme',
      }],
      total: 1,
    });
  });

  it('loads real leads and returns the selected ID', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <EntityReferenceSelect entityType="Lead" value="" onChange={onChange} />,
      { wrapper: Wrapper },
    );

    await user.click(screen.getByRole('combobox', { name: 'Select Lead' }));
    await user.click(await screen.findByText('Jane Doe'));

    expect(fetchLeadsApiMock).toHaveBeenCalledWith({ page: 1, limit: 50, search: undefined });
    expect(onChange).toHaveBeenCalledWith('lead-1', 'Jane Doe');
  });

  it('does not query an entity endpoint without its read permission', () => {
    render(
      <EntityReferenceSelect entityType="Contact" value="" onChange={vi.fn()} />,
      { wrapper: Wrapper },
    );

    expect(screen.getByRole('combobox', { name: 'Select Contact' })).toBeDisabled();
    expect(screen.getByText('No permission to view contacts')).toBeInTheDocument();
    expect(fetchContactsApiMock).not.toHaveBeenCalled();
  });
});
