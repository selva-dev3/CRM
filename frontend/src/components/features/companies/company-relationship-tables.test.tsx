import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import {
  CompanyContactsTable,
  CompanyDocumentsTable,
  CompanyInvoicesTable,
  CompanyQuotesTable,
  CompanyRelationshipError,
} from './company-relationship-tables';

describe('Company relationship tables', () => {
  it('renders canonical contact fields and opens the selected record', async () => {
    const onRowClick = vi.fn();
    render(
      <CompanyContactsTable
        data={[
          {
            id: 'contact-1',
            name: 'Jane Buyer',
            email: 'jane@example.test',
            phone: '555-0100',
            position: 'CTO',
            created_at: '2026-09-06T10:00:00Z',
          },
        ]}
        isLoading={false}
        onRowClick={onRowClick}
      />,
    );

    expect(screen.getByText('CTO')).toBeInTheDocument();
    expect(screen.getByText('jane@example.test')).toBeInTheDocument();
    await userEvent.click(screen.getByText('Jane Buyer'));
    expect(onRowClick).toHaveBeenCalledWith(expect.objectContaining({ id: 'contact-1' }));
  });

  it('uses quote and invoice numbers instead of internal IDs', () => {
    const { rerender } = render(
      <CompanyQuotesTable
        data={[
          {
            id: 'quote-internal-id',
            quote_number: 'QUO-2026-000010',
            total_amount: 10000,
            currency: 'INR',
            status: 'Accepted',
            created_at: '2026-09-06T10:00:00Z',
          },
        ]}
        isLoading={false}
      />,
    );

    expect(screen.getByText('QUO-2026-000010')).toBeInTheDocument();
    expect(screen.queryByText('quote-internal-id')).not.toBeInTheDocument();

    rerender(
      <CompanyInvoicesTable
        data={[
          {
            id: 'invoice-internal-id',
            invoice_number: 'INV-2026-000005',
            amount: 10000,
            outstanding_amount: 2500,
            currency: 'INR',
            status: 'Accepted',
            payment_status: 'Partially Paid',
          },
        ]}
        isLoading={false}
      />,
    );

    expect(screen.getByText('INV-2026-000005')).toBeInTheDocument();
    expect(screen.getByText('Partially Paid')).toBeInTheDocument();
    expect(screen.queryByText('invoice-internal-id')).not.toBeInTheDocument();
  });

  it('renders canonical document fields and an accessible download link', () => {
    render(
      <CompanyDocumentsTable
        data={[
          {
            id: 'document-1',
            filename: 'contract.pdf',
            file_size: 2048,
            mime_type: 'application/pdf',
            download_url: 'https://files.example.test/contract.pdf',
            uploaded_at: '2026-09-06T10:00:00Z',
          },
        ]}
        isLoading={false}
      />,
    );

    expect(screen.getByText('contract.pdf')).toBeInTheDocument();
    expect(screen.getByText('2.0 KB')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Download' })).toHaveAttribute(
      'href',
      'https://files.example.test/contract.pdf',
    );
  });

  it('does not offer a pointless retry for a known unavailable relationship', () => {
    render(
      <CompanyRelationshipError
        resourceName="Documents"
        unavailable
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Documents are not linked to companies yet.',
    );
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
  });
});
