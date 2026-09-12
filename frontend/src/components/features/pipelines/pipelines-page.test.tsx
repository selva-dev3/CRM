import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  hasPermission: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
}));

vi.mock('@/hooks/use-has-permission', () => ({
  useHasPermission: () => ({ hasPermission: mocks.hasPermission }),
}));
vi.mock('@/lib/api/deals', () => ({
  useDealStagesQuery: () => ({
    data: [
      { id: 'stage-1', name: 'Prospecting', probability: 10 },
      { id: 'stage-2', name: 'Qualification', probability: 30 },
    ],
    isLoading: false,
  }),
  useKanbanBoardQuery: () => ({
    data: {
      Prospecting: [{ id: 'deal-1', title: 'Expansion', amount: 2500 }],
    },
    isLoading: false,
  }),
  useCreateDealStageMutation: () => ({ mutateAsync: mocks.create, isPending: false }),
  useUpdateDealStageMutation: () => ({ mutateAsync: mocks.update, isPending: false }),
}));

import PipelinesPage from './pipelines-page';

describe('pipelines page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.hasPermission.mockReturnValue(false);
  });
  afterEach(cleanup);

  it('shows pipeline data without exposing mutation controls to read-only users', () => {
    render(<PipelinesPage />);

    expect(screen.getByRole('heading', { name: 'Pipelines' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Expansion' })).toHaveAttribute('href', '/deals/deal-1');
    expect(screen.queryByRole('button', { name: /add stage/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  });

  it('shows existing permission-gated pipeline controls to editors', () => {
    mocks.hasPermission.mockReturnValue(true);
    render(<PipelinesPage />);

    expect(screen.getByRole('button', { name: /add stage/i })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Move Expansion to stage' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /add stage/i }));
    expect(screen.getByRole('dialog', { name: 'Add Pipeline Stage' })).toBeInTheDocument();
  });
});
