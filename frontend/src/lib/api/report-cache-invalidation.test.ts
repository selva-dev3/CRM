import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  invalidateQueries: vi.fn(),
  mutationOptions: [] as Array<{ onSuccess?: (...args: unknown[]) => void }>,
}));

vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn(),
  useQueryClient: () => ({ invalidateQueries: mocks.invalidateQueries }),
  useMutation: (options: { onSuccess?: (...args: unknown[]) => void }) => {
    mocks.mutationOptions.push(options);
    return {};
  },
}));

import { useMarkDealWonMutation } from './deals';
import { useCreateInvoiceMutation } from './invoices';
import { useCreateQuoteMutation } from './quotes';

describe('financial workflow report cache invalidation', () => {
  beforeEach(() => {
    mocks.invalidateQueries.mockClear();
    mocks.mutationOptions.length = 0;
  });

  it('invalidates reports after deal-won automation creates a quote', () => {
    useMarkDealWonMutation();
    mocks.mutationOptions[0].onSuccess?.({}, { id: 'deal-1' });

    expect(mocks.invalidateQueries).toHaveBeenCalledWith({ queryKey: ['reports'] });
    expect(mocks.invalidateQueries).toHaveBeenCalledWith({ queryKey: ['quotes'] });
  });

  it('invalidates reports after quote and invoice creation', () => {
    useCreateQuoteMutation();
    mocks.mutationOptions[0].onSuccess?.({});
    useCreateInvoiceMutation();
    mocks.mutationOptions[1].onSuccess?.({});

    expect(mocks.invalidateQueries).toHaveBeenCalledTimes(4);
    expect(mocks.invalidateQueries).toHaveBeenNthCalledWith(2, { queryKey: ['reports'] });
    expect(mocks.invalidateQueries).toHaveBeenNthCalledWith(4, { queryKey: ['reports'] });
  });
});
