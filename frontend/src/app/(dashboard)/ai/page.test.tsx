import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AIIntelligencePage from './page';

const mocks = vi.hoisted(() => ({
  canGenerate: true,
  getUsageStats: vi.fn(),
  searchCRM: vi.fn(),
  generateEmail: vi.fn(),
}));

vi.mock('@/hooks/use-has-permission', () => ({
  useHasPermission: () => ({
    hasPermission: (permission: string) =>
      permission === 'ai:read' || (permission === 'ai:generate' && mocks.canGenerate),
  }),
}));

vi.mock('@/lib/api/ai', () => ({
  aiService: {
    getUsageStats: mocks.getUsageStats,
    searchCRM: mocks.searchCRM,
    generateEmail: mocks.generateEmail,
  },
}));

describe('AIIntelligencePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.canGenerate = true;
    mocks.getUsageStats.mockResolvedValue({
      request_count: 3,
      tokens_used_this_month: 120,
      estimated_cost_usd: 0.0123,
    });
  });

  it('runs tenant-safe CRM search and renders real API results', async () => {
    mocks.searchCRM.mockResolvedValue({
      query: 'Acme',
      plan: {
        entity_type: 'company',
        limit: 20,
      },
      result_count: 1,
      results: [{ id: 'company-1', name: 'Acme' }],
      explanation: 'One authorized company matched.',
      run_id: 'run-1',
    });
    render(<AIIntelligencePage />);

    fireEvent.change(screen.getByLabelText('Question'), { target: { value: 'Acme' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search authorized CRM data' }));

    await waitFor(() => expect(mocks.searchCRM).toHaveBeenCalledWith('Acme', undefined));
    expect(await screen.findByText('One authorized company matched.')).toBeInTheDocument();
    expect(screen.getByText('Acme')).toBeInTheDocument();
  });

  it('allows an explicit record type while defaulting to automatic intent detection', async () => {
    mocks.searchCRM.mockResolvedValue({
      query: 'How many open deals are there?',
      plan: { intent: 'count', entity_type: 'deal', filters: [], sort_direction: 'asc', limit: 20 },
      result_count: 4,
      results: [{ count: 4 }],
      explanation: 'There are 4 matching deal record(s).',
      run_id: 'run-3',
    });
    render(<AIIntelligencePage />);

    expect(screen.getByLabelText('Record type')).toHaveValue('auto');
    fireEvent.change(screen.getByLabelText('Record type'), { target: { value: 'deal' } });
    fireEvent.change(screen.getByLabelText('Question'), {
      target: { value: 'How many open deals are there?' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Search authorized CRM data' }));

    await waitFor(() =>
      expect(mocks.searchCRM).toHaveBeenCalledWith('How many open deals are there?', 'deal'),
    );
    expect(await screen.findByText('There are 4 matching deal record(s).')).toBeInTheDocument();
  });

  it('shows a provider failure and allows the search to be retried', async () => {
    mocks.searchCRM
      .mockRejectedValueOnce(new Error('The configured AI provider credentials were rejected.'))
      .mockResolvedValueOnce({
        query: 'Acme',
        plan: { entity_type: 'company', limit: 20 },
        result_count: 0,
        results: [],
        explanation: 'Found 0 authorized company record(s) matching the validated search plan.',
        run_id: 'run-2',
      });
    render(<AIIntelligencePage />);

    fireEvent.change(screen.getByLabelText('Question'), { target: { value: 'Acme' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search authorized CRM data' }));

    expect(
      await screen.findByText('The configured AI provider credentials were rejected.'),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    await waitFor(() => expect(mocks.searchCRM).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('No matching records.')).toBeInTheDocument();
  });

  it('does not allow generation without ai:generate', async () => {
    mocks.canGenerate = false;
    render(<AIIntelligencePage />);

    expect(screen.getByText(/cannot run AI operations/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Generate email' })).toBeDisabled();
    expect(mocks.generateEmail).not.toHaveBeenCalled();
  });
});
