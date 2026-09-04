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
      entity_type: 'company',
      result_count: 1,
      results: [{ id: 'company-1', name: 'Acme' }],
      explanation: 'One authorized company matched.',
    });
    render(<AIIntelligencePage />);

    fireEvent.change(screen.getByLabelText('Question'), { target: { value: 'Acme' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search authorized CRM data' }));

    await waitFor(() => expect(mocks.searchCRM).toHaveBeenCalledWith('Acme', 'company'));
    expect(await screen.findByText('One authorized company matched.')).toBeInTheDocument();
    expect(screen.getByText('Acme')).toBeInTheDocument();
  });

  it('does not allow generation without ai:generate', async () => {
    mocks.canGenerate = false;
    render(<AIIntelligencePage />);

    expect(screen.getByText(/cannot run AI operations/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Generate email' })).toBeDisabled();
    expect(mocks.generateEmail).not.toHaveBeenCalled();
  });
});
