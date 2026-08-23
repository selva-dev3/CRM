import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import PaymentSuccessPage from './page';

const mockPush = vi.fn();
const mockInvalidateQueries = vi.fn();
const mockRefetch = vi.fn();
const mockRefetchVerify = vi.fn();

let mockSearchParamsSessionId: string | null = 'cs_test_session_12345';
let mockSearchParamsOrgId: string | null = 'org-123';

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  useSearchParams: () => ({
    get: vi.fn().mockImplementation((param: string) => {
      if (param === 'session_id') return mockSearchParamsSessionId;
      if (param === 'org_id') return mockSearchParamsOrgId;
      return null;
    }),
  }),
}));

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({
    invalidateQueries: mockInvalidateQueries,
  }),
}));

import type { SubscriptionCheckoutVerifyResponse } from '@/lib/api/organizations';

const mockVerifyResult: {
  data: SubscriptionCheckoutVerifyResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  refetch: typeof mockRefetchVerify;
} = {
  data: {
    verified: true,
    db_synced: true,
    plan: 'Starter',
    plan_slug: 'starter',
    status: 'success',
    message: 'Payment verified successfully.',
  },
  isLoading: false,
  isError: false,
  refetch: mockRefetchVerify,
};

vi.mock('@/lib/api/organizations', () => ({
  useVerifySubscriptionCheckoutQuery: () => mockVerifyResult,
  useOrganizationSubscriptionQuery: () => ({
    data: { plan: 'Starter', billing_cycle: 'Monthly', amount: 999 },
    isLoading: false,
    refetch: mockRefetch,
  }),
  useCurrentOrganizationQuery: () => ({
    data: { id: 'org-123', name: 'Acme Corp', plan: 'Starter' },
  }),
}));

describe('PaymentSuccessPage - Backend Verification Flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSearchParamsSessionId = 'cs_test_session_12345';
    mockSearchParamsOrgId = 'org-123';
    mockVerifyResult.isLoading = false;
    mockVerifyResult.isError = false;
    mockVerifyResult.data = {
      verified: true,
      db_synced: true,
      plan: 'Starter',
      plan_slug: 'starter',
      status: 'success',
      message: 'Payment verified successfully.',
    };
  });

  it('renders verified payment status when verification succeeds and DB is synced', () => {
    render(<PaymentSuccessPage />);

    expect(screen.getByText('Subscription Upgraded!')).toBeInTheDocument();
    expect(screen.getByText(/Stripe Payment Verified/i)).toBeInTheDocument();
    expect(screen.getByText('Starter')).toBeInTheDocument();
    expect(screen.getByText('Acme Corp')).toBeInTheDocument();
    expect(screen.getByText('cs_test_session_12345')).toBeInTheDocument();
  });

  it('renders verification loading state while query is in-flight', () => {
    mockVerifyResult.isLoading = true;

    render(<PaymentSuccessPage />);

    expect(screen.getByText('Verifying Payment Status')).toBeInTheDocument();
    expect(screen.getByText(/Checking cryptographic payment verification/i)).toBeInTheDocument();
  });

  it('renders pending synchronization state when verified by Stripe but DB sync is in-flight', () => {
    mockVerifyResult.data = {
      verified: true,
      db_synced: false,
      plan: 'Starter',
      plan_slug: 'starter',
      status: 'success',
      message: 'Payment verified successfully.',
    };

    render(<PaymentSuccessPage />);

    expect(screen.getByText('Activating Your Subscription')).toBeInTheDocument();
    expect(screen.getByText(/Payment Confirmed · Syncing/i)).toBeInTheDocument();
    expect(screen.getByText('Synchronizing...')).toBeInTheDocument();
  });

  it('renders verification failure alert when session is fake or payment unverified', () => {
    mockVerifyResult.data = {
      verified: false,
      db_synced: false,
      plan: null,
      plan_slug: null,
      status: 'unpaid',
      message: 'Payment is not confirmed (status: unpaid).',
    };

    render(<PaymentSuccessPage />);

    expect(screen.getByText('Payment Not Verified')).toBeInTheDocument();
    expect(screen.getByText('Payment is not confirmed (status: unpaid).')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Back to Billing/i })).toBeInTheDocument();
  });

  it('invalidates React Query caches on verified and synced mount', () => {
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
