import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  query: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mocks.push }),
}));
vi.mock('@/lib/api/activities', async (importOriginal) => ({
  ...await importOriginal<typeof import('@/lib/api/activities')>(),
  useActivitiesPageQuery: mocks.query,
}));

import ActivitiesPage from './activities-page';

describe('activities page', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('renders activity context and opens the related record', () => {
    mocks.query.mockReturnValue({
      data: {
        items: [{
          id: 'calls:call-1',
          module: 'calls',
          action: 'Outbound',
          description: 'Discovery call',
          entity_type: 'call',
          entity_id: 'call-1',
          occurred_at: '2026-09-12T10:00:00Z',
          href: '/calls/call-1',
        }],
        total: 1,
      },
      isLoading: false,
    });
    render(<ActivitiesPage />);

    expect(screen.getByText('Discovery call')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Discovery call').closest('tr')!);
    expect(mocks.push).toHaveBeenCalledWith('/calls/call-1');
  });

  it('shows backend errors instead of presenting an empty feed', () => {
    mocks.query.mockReturnValue({
      isLoading: false,
      isError: true,
      error: new Error('Feed unavailable'),
    });
    render(<ActivitiesPage />);

    expect(screen.getByRole('alert')).toHaveTextContent('Feed unavailable');
  });
});
