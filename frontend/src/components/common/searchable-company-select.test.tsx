import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { SearchableCompanySelect } from './searchable-company-select';

const companies = [
  { id: 'company-1', name: 'Acme Corporation' },
  { id: 'company-2', name: 'Beta Industries' },
];

describe('SearchableCompanySelect', () => {
  it('preserves the selected label and filters companies by name', async () => {
    const user = userEvent.setup();
    render(<SearchableCompanySelect value="company-1" onChange={vi.fn()} companies={companies} />);

    expect(screen.getByRole('combobox', { name: /Acme Corporation/ })).toBeInTheDocument();
    await user.click(screen.getByRole('combobox', { name: /Acme Corporation/ }));
    await user.type(screen.getByPlaceholderText('Search company by name...'), 'beta');

    expect(screen.getByRole('option', { name: 'Beta Industries' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Acme Corporation' })).not.toBeInTheDocument();
  });

  it('selects and clears a company', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<SearchableCompanySelect value="" onChange={onChange} companies={companies} />);

    await user.click(screen.getByRole('combobox', { name: /Select Company/ }));
    await user.click(screen.getByRole('option', { name: 'Beta Industries' }));
    expect(onChange).toHaveBeenCalledWith('company-2');

    await user.click(screen.getByRole('combobox', { name: /Select Company/ }));
    await user.click(screen.getByRole('option', { name: /None \/ Clear Selection/ }));
    expect(onChange).toHaveBeenLastCalledWith('');
  });

  it('shows an empty state when no company matches', async () => {
    const user = userEvent.setup();
    render(<SearchableCompanySelect value="" onChange={vi.fn()} companies={companies} />);

    await user.click(screen.getByRole('combobox', { name: /Select Company/ }));
    await user.type(screen.getByPlaceholderText('Search company by name...'), 'missing');

    expect(screen.getByText('No matching companies')).toBeInTheDocument();
  });

  it('connects a custom field label to the combobox trigger', () => {
    render(
      <div>
        <label htmlFor="contact-company">Company</label>
        <SearchableCompanySelect
          id="contact-company"
          ariaLabel="Select company for contact"
          value="company-1"
          onChange={vi.fn()}
          companies={companies}
        />
      </div>,
    );

    expect(screen.getByRole('combobox', { name: /Select company for contact: Acme Corporation/ }))
      .toHaveAttribute('id', 'contact-company');
  });
});
