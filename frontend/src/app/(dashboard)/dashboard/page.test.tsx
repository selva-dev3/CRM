import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const refetch = vi.fn();
const mutateAsync = vi.fn();

const queryResult = <T,>(data: T) => ({
  data,
  isLoading: false,
  isError: false,
  isFetching: false,
  refetch,
});

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock('@/lib/api/dashboard', () => ({
  useDashboardKpisQuery: () => queryResult({
    total_leads: 7,
    deals_won_amount: 5000,
    pipeline_revenue: 0,
    win_rate_percentage: 100,
    won_deals_count: 1,
    closed_deals_count: 1,
    ai_lead_score_avg: 0,
    scored_leads_count: 7,
  }),
  useSalesFunnelQuery: () => queryResult([
    { stage: 'Prospecting', count: 0, value: 0 },
    { stage: 'Closed Won', count: 1, value: 5000 },
  ]),
  useTopPerformersQuery: () => queryResult([]),
  useLeadConversionsQuery: () => queryResult([
    { source: 'selv.in', leads: 2, converted: 0, rate: 0 },
  ]),
  useActivitiesSummaryQuery: () => queryResult({
    calls_completed: 1,
    emails_sent: 1,
    meetings_held: 0,
    tasks_completed: 0,
    period_label: 'Today · Asia/Kolkata',
  }),
  useRecentDealsQuery: () => queryResult([]),
  useDashboardAiInsightsQuery: () => queryResult(undefined),
  useCustomWidgetsQuery: () => queryResult([]),
  useSaveCustomWidgetsMutation: () => ({ mutateAsync, isPending: false }),
}));

import DashboardPage from './page';

describe('DashboardPage metric presentation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows factual KPI context without hard-coded positive trends', () => {
    render(<DashboardPage />);

    expect(screen.getByText('1 of 1 closed won')).toBeInTheDocument();
    expect(screen.getByText('Across 7 scored leads')).toBeInTheDocument();
    expect(screen.getByText('Needs Attention')).toBeInTheDocument();
    expect(screen.queryByText('Optimal')).not.toBeInTheDocument();
    expect(screen.queryByText('+12.5%')).not.toBeInTheDocument();
  });

  it('renders a zero-value funnel stage with an empty progress bar', () => {
    render(<DashboardPage />);

    expect(screen.getByRole('progressbar', { name: 'Prospecting pipeline value' })).toHaveStyle({
      width: '0%',
    });
  });

  it('shows the organization-local activity period', () => {
    render(<DashboardPage />);

    expect(screen.getByText('Today · Asia/Kolkata')).toBeInTheDocument();
  });
});
