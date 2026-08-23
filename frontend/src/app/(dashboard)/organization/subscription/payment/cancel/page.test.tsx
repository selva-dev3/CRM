import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import PaymentCancelPage from './page';

const mockPush = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  useSearchParams: () => ({
    get: vi.fn().mockImplementation((param: string) => {
      if (param === 'org_id') return 'org-123';
      return null;
    }),
  }),
}));

vi.mock('@/lib/api/organizations', () => ({
  useCurrentOrganizationQuery: () => ({
    data: { id: 'org-123', name: 'Acme Corp', plan: 'Free' },
  }),
}));

describe('PaymentCancelPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders payment cancellation message and keeps current plan intact', () => {
    render(<PaymentCancelPage />);

    expect(screen.getByText('Upgrade Incomplete')).toBeInTheDocument();
    expect(screen.getByText('Payment Cancelled')).toBeInTheDocument();
    expect(
      screen.getByText(/Your Stripe checkout session was cancelled/i)
    ).toBeInTheDocument();
    expect(screen.getByText('Current Plan Intact')).toBeInTheDocument();
  });

  it('navigates to plan selection page when clicking Choose Another Plan', () => {
    render(<PaymentCancelPage />);

    const retryBtn = screen.getByRole('button', { name: /Choose Another Plan/i });
    fireEvent.click(retryBtn);

    expect(mockPush).toHaveBeenCalledWith('/organization/subscription/plans?org_id=org-123');
  });

  it('navigates back to organization when clicking Back to Organization', () => {
    render(<PaymentCancelPage />);

    const returnBtn = screen.getByRole('button', { name: /Back to Organization/i });
    fireEvent.click(returnBtn);

    expect(mockPush).toHaveBeenCalledWith('/organization/org-123');
  });
});
