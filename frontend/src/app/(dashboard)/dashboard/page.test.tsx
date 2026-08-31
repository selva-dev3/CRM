import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  kpis: vi.fn(),
  funnel: vi.fn(),
  performers: vi.fn(),
  conversions: vi.fn(),
  activities: vi.fn(),
  deals: vi.fn(),
  insights: vi.fn(),
  widgets: vi.fn(),
  mutateAsync: vi.fn(),
  routerPush: vi.fn(),
}));

const refetch = vi.fn();

const queryResult = <T,>(data: T, overrides = {}) => ({
  data,
  isLoading: false,
  isError: false,
  isFetching: false,
  refetch,
  ...overrides,
});

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mocks.routerPush }),
}));

vi.mock('@/lib/api/dashboard', () => ({
  useDashboardKpisQuery: () => mocks.kpis(),
  useSalesFunnelQuery: () => mocks.funnel(),
  useTopPerformersQuery: () => mocks.performers(),
  useLeadConversionsQuery: () => mocks.conversions(),
  useActivitiesSummaryQuery: () => mocks.activities(),
  useRecentDealsQuery: () => mocks.deals(),
  useDashboardAiInsightsQuery: () => mocks.insights(),
  useCustomWidgetsQuery: () => mocks.widgets(),
  useSaveCustomWidgetsMutation: () => ({
    mutateAsync: mocks.mutateAsync,
    isPending: false,
  }),
}));

import DashboardPage from './page';

const defaultWidgets = [
  { id: 'w-kpis', title: 'Executive KPIs', enabled: true },
  { id: 'w-funnel', title: 'Sales Stage Funnel', enabled: true },
  { id: 'w-top', title: 'Top Sales Performers', enabled: true },
  { id: 'w-deals', title: 'Priority Deals', enabled: true },
  { id: 'w-ai', title: 'AI Recommendations', enabled: true },
];

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.mutateAsync.mockResolvedValue({ status: 'success', message: 'Saved' });
    mocks.kpis.mockReturnValue(queryResult({
      total_leads: 7,
      deals_won_amount: 5000,
      pipeline_revenue: 0,
      win_rate_percentage: 100,
      won_deals_count: 1,
      closed_deals_count: 1,
      ai_lead_score_avg: 0,
      scored_leads_count: 7,
    }));
    mocks.funnel.mockReturnValue(queryResult([
      { stage: 'Prospecting', count: 0, value: 0 },
      { stage: 'Closed Won', count: 1, value: 5000 },
    ]));
    mocks.performers.mockReturnValue(queryResult([]));
    mocks.conversions.mockReturnValue(queryResult([
      { source: 'selv.in', leads: 2, converted: 0, rate: 0 },
    ]));
    mocks.activities.mockReturnValue(queryResult({
      calls_completed: 1,
      emails_sent: 1,
      meetings_held: 0,
      tasks_completed: 0,
      period_label: 'Today · Asia/Kolkata',
    }));
    mocks.deals.mockReturnValue(queryResult([]));
    mocks.insights.mockReturnValue(queryResult(undefined));
    mocks.widgets.mockReturnValue(queryResult(defaultWidgets));
  });

  it('shows factual KPI context without hard-coded positive trends', () => {
    render(<DashboardPage />);

    expect(screen.getByText('1 of 1 closed won')).toBeInTheDocument();
    expect(screen.getByText('Across 7 scored leads')).toBeInTheDocument();
    expect(screen.getByText('Needs Attention')).toBeInTheDocument();
    expect(screen.queryByText('Optimal')).not.toBeInTheDocument();
    expect(screen.queryByText('+12.5%')).not.toBeInTheDocument();
  });

  it('renders loading, error, and empty states', () => {
    mocks.kpis.mockReturnValue(queryResult(undefined, { isLoading: true }));
    mocks.funnel.mockReturnValue(queryResult([]));
    mocks.activities.mockReturnValue(queryResult(undefined, { isError: true }));

    const { container } = render(<DashboardPage />);

    expect(container.querySelector('.animate-pulse')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('activity summary could not be loaded');
    expect(screen.getByText('No deals are available yet.')).toBeInTheDocument();
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

  it('links each populated opportunity to its detail page', () => {
    mocks.deals.mockReturnValue(queryResult([{
      deal_id: 'deal-123',
      title: 'Enterprise renewal',
      amount: 5000,
      stage: 'Negotiation',
      owner: 'Grace Hopper',
      updated_at: '2026-08-31',
    }]));

    render(<DashboardPage />);

    expect(screen.getByRole('link', { name: 'Enterprise renewal' })).toHaveAttribute(
      'href',
      '/deals/deal-123',
    );
  });

  it('applies disabled widget preferences to dashboard sections', () => {
    mocks.widgets.mockReturnValue(queryResult(
      defaultWidgets.map((widget) => (
        widget.id === 'w-kpis' ? { ...widget, enabled: false } : widget
      )),
    ));

    render(<DashboardPage />);

    expect(screen.queryByText('Total Active Leads')).not.toBeInTheDocument();
    expect(screen.getByText('Sales Stage Funnel')).toBeInTheDocument();
  });

  it('opens the deal referenced by an AI insight', () => {
    mocks.insights.mockReturnValue(queryResult({
      summary: 'One opportunity needs attention.',
      insights: [{
        title: 'Follow up with Enterprise renewal',
        description: 'High value opportunity.',
        type: 'high',
        action: 'Follow Up',
        deal_id: 'deal-123',
      }],
      risk_deals: [],
    }));

    render(<DashboardPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Follow Up' }));

    expect(mocks.routerPush).toHaveBeenCalledWith('/deals/deal-123');
  });

  it('falls back to the deals list for legacy AI insights without a deal id', () => {
    mocks.insights.mockReturnValue(queryResult({
      summary: 'One opportunity needs attention.',
      insights: [{
        title: 'Review pipeline',
        description: 'Review the latest opportunities.',
        type: 'info',
        action: 'Follow Up',
      }],
      risk_deals: [],
    }));

    render(<DashboardPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Follow Up' }));

    expect(mocks.routerPush).toHaveBeenCalledWith('/deals');
  });

  it('provides an accessible success-message dismiss control', async () => {
    render(<DashboardPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Customize Widgets' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save Layout' }));

    expect(await screen.findByRole('button', { name: 'Dismiss success message' })).toBeInTheDocument();
    await waitFor(() => expect(refetch).toHaveBeenCalled());
  });
});
