import { describe, expect, it, vi } from 'vitest';

const queryMocks = vi.hoisted(() => ({
  invalidateQueries: vi.fn(),
  useMutation: vi.fn(),
  onSuccess: undefined as (() => void) | undefined,
}));

vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn(),
  useQueryClient: () => ({ invalidateQueries: queryMocks.invalidateQueries }),
  useMutation: (options: { onSuccess?: () => void }) => {
    queryMocks.useMutation(options);
    queryMocks.onSuccess = options.onSuccess;
    return {};
  },
}));

import { approveQuoteApi } from './quotes';

describe('automatic quote workflow API', () => {
  it('retains internal approval as the intentional manual control', () => {
    expect(approveQuoteApi).toBeTypeOf('function');
  });
});
