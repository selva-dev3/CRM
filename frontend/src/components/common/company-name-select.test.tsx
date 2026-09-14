import { useState } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  useQuery: vi.fn(),
  fetchCompanies: vi.fn(),
}));

vi.mock('@tanstack/react-query', () => ({
  useQuery: mocks.useQuery,
}));

vi.mock('@/lib/api/companies', () => ({
  companyKeys: { list: (...args: unknown[]) => ['companies', ...args] },
  fetchCompaniesApi: mocks.fetchCompanies,
}));

import { CompanyNameSelect } from './company-name-select';

const availableCompanies = [
  { id: 'company-1', name: 'Acme Corporation' },
  { id: 'company-2', name: 'Beta Industries' },
];

function TestHarness() {
  const [value, setValue] = useState('');
  return <CompanyNameSelect id="company" value={value} onChange={setValue} />;
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.useQuery.mockImplementation(({ queryKey }: { queryKey: readonly unknown[] }) => {
    const search = String(queryKey[3] ?? '').toLowerCase();
    return {
      data: availableCompanies.filter((company) => company.name.toLowerCase().includes(search)),
      isLoading: false,
      isError: false,
    };
  });
});

describe('CompanyNameSelect', () => {
  it('shows matching company names and writes the selected name to the form', async () => {
    const user = userEvent.setup();
    render(<TestHarness />);

    const input = screen.getByRole('combobox');
    await user.click(input);
    await user.type(input, 'beta');

    expect(await screen.findByRole('option', { name: 'Beta Industries' })).toBeVisible();
    await waitFor(() => {
      expect(screen.queryByRole('option', { name: 'Acme Corporation' })).not.toBeInTheDocument();
    });

    await user.click(screen.getByRole('option', { name: 'Beta Industries' }));
    await waitFor(() => expect(screen.getByRole('combobox')).toHaveValue('Beta Industries'));
  });

  it('allows free-form company names when no match exists', async () => {
    const user = userEvent.setup();
    render(<TestHarness />);

    await user.type(screen.getByRole('combobox'), 'New Company');

    expect(screen.getByRole('combobox')).toHaveValue('New Company');
    expect(await screen.findByText('No matching companies')).toBeVisible();
  });
});
