import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const postMock = vi.fn();

vi.mock('@/lib/api/client', () => ({
  apiClient: {
    post: (...args: unknown[]) => postMock(...args),
  },
}));

import { useCreateNoteMutation } from './notes';

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return {
    client,
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  };
}

describe('useCreateNoteMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it.each([
    ['Lead', 'lead', 'lead-1'],
    ['Contact', 'contact', 'contact-1'],
    ['Deal', 'deal', 'deal-1'],
    ['Company', 'company', 'company-1'],
  ] as const)('normalizes %s and invalidates its matching detail cache', async (label, entityType, entityId) => {
    postMock.mockResolvedValue({
      id: 'note-1',
      entity_type: entityType,
      entity_id: entityId,
      content: 'Follow up',
      created_at: '2026-09-15T10:00:00Z',
    });
    const { client, wrapper } = createWrapper();
    const detailKey = [`${entityType}-notes`, entityId, 1, 15] as const;
    client.setQueryData(detailKey, { items: [], total: 0 });

    const { result } = renderHook(() => useCreateNoteMutation(), { wrapper });
    await result.current.mutateAsync({
      entity_type: label,
      entity_id: entityId,
      content: 'Follow up',
    });

    expect(postMock).toHaveBeenCalledWith('/notes', {
      entity_type: entityType,
      entity_id: entityId,
      content: 'Follow up',
    });
    await waitFor(() => {
      expect(client.getQueryState(detailKey)?.isInvalidated).toBe(true);
    });
  });
});
