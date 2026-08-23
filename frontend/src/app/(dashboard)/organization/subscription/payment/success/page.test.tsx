import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import PaymentSuccessPage from './page';

const mockPush = vi.fn();
const mockInvalidateQueries = vi.fn();
const mockRefetch = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  useSearchParams: () => ({
    get: vi.fn().mockImplementation((param: string) => {
      if (param === 'session_id') return 'cs_test_session_12345';
      if (param === 'org_id') return 'org-123';
      return null;
    }),
  }),
}));

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({
    invalidateQueries: mockInvalidateQueries,
  }),
}));

vi.mock('@/lib/api/organizations', () => ({
  useOrganizationSubscriptionQuery: () => ({
    data: { plan: 'Starter', billing_cycle: 'Monthly', amount: 999 },
    isLoading: false,
    refetch: mockRefetch,
  }),
  useCurrentOrganizationQuery: () => ({
    data: { id: 'org-123', name: 'Acme Corp', plan: 'Starter' },
  }),
}));

describe('PaymentSuccessPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders verified payment status and updated subscription tier', () => {
    render(<PaymentSuccessPage />);

    expect(screen.getByText('Subscription Upgraded!')).toBeInTheDocument();
    expect(screen.getByText(/Stripe Payment Verified/i)).toBeInTheDocument();
    expect(screen.getByText('Starter')).toBeInTheDocument();
    expect(screen.getByText('Acme Corp')).toBeInTheDocument();
    expect(screen.getByText('cs_test_session_12345')).toBeInTheDocument();
  });

  it('invalidates React Query caches on mount', () => {
    render(<PaymentSuccessPage />);

    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ['organization-subscription'],
    });
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ['current-organization'],
    });
    expect(mockRefetch).toHaveBeenCalled();
  });

  it('navigates back to organization on button click', () => {
    render(<PaymentSuccessPage />);

    const returnBtn = screen.getByRole('button', { name: /Return to Subscription & Billing/i });
    fireEvent.click(returnBtn);

    expect(mockPush).toHaveBeenCalledWith('/organization/org-123');
  });
});
