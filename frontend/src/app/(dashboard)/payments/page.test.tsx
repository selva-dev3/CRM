import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';

import PaymentsPage from './page';

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  query: vi.fn(),
}));

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: mocks.push }) }));
vi.mock('@/hooks/use-has-permission', () => ({
  useHasPermission: () => ({ hasPermission: () => false }),
}));
vi.mock('@/components/features/payments/AddPaymentDialog', () => ({
  AddPaymentDialog: () => null,
}));
vi.mock('@/lib/api/payments', () => ({
  useInvoicePaymentSummariesPageQuery: (...args: unknown[]) => mocks.query(...args),
}));
vi.mock('@/components/common/data-table', () => ({
  DataTable: ({ columns, data }: { columns: Array<{ id: string; cell: (item: Record<string, unknown>) => ReactNode }>; data: Array<Record<string, unknown>> }) => (
    <div>
      {data.map((item) => (
        <div key={String(item.id)}>
          {columns.map((column) => <div key={column.id}>{column.cell(item)}</div>)}
        </div>
      ))}
    </div>
  ),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

it('renders an accepted invoice with no payment as backend-derived Pending', () => {
  mocks.query.mockReturnValue({
    data: {
      items: [{
        id: 'invoice-1', invoice_id: 'invoice-1', invoice_number: 'INV-2026-000007',
        company_name: 'New Company', amount: '1000.00', paid_amount: '0.00',
        outstanding_amount: '1000.00', currency: 'INR', payment_status: 'Pending',
        latest_payment_id: null, payment_number: null, payment_date: null,
      }],
      total: 1,
    },
    error: null, isLoading: false, isFetching: false, refetch: vi.fn(),
  });

  render(<PaymentsPage />);

  expect(screen.getByText('INV-2026-000007')).toBeInTheDocument();
  expect(screen.getByText('New Company')).toBeInTheDocument();
  expect(screen.getByText('Pending')).toBeInTheDocument();
  expect(screen.getByText('No payment recorded')).toBeInTheDocument();
  expect(screen.getAllByText('₹0.00')).toHaveLength(1);
  expect(screen.getAllByText('₹1,000.00')).toHaveLength(2);
  expect(screen.getAllByText('—').length).toBeGreaterThan(0);
});

it('renders Paid from the authoritative invoice summary after full payment', () => {
  mocks.query.mockReturnValue({
    data: {
      items: [{
        id: 'invoice-1', invoice_id: 'invoice-1', invoice_number: 'INV-2026-000007',
        company_name: 'New Company', amount: '1000.00', paid_amount: '1000.00',
        outstanding_amount: '0.00', currency: 'INR', payment_status: 'Paid',
        latest_payment_id: 'payment-1', payment_number: 'PAY-2026-000003',
        payment_type: 'Bank Transfer', payment_date: '2026-09-07', notes: 'Received',
      }],
      total: 1,
    },
    error: null, isLoading: false, isFetching: false, refetch: vi.fn(),
  });

  render(<PaymentsPage />);

  expect(screen.getByText('Paid')).toBeInTheDocument();
  expect(screen.getByText('PAY-2026-000003')).toBeInTheDocument();
  expect(screen.getByText('Received')).toBeInTheDocument();
  expect(screen.getAllByText('₹1,000.00')).toHaveLength(2);
  expect(screen.getByText('₹0.00')).toBeInTheDocument();
});
