import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

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

import { useConvertQuoteToInvoiceMutation } from './quotes';

describe('useConvertQuoteToInvoiceMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryMocks.onSuccess = undefined;
  });

  it('invalidates both Quote and Invoice query hierarchies after conversion', () => {
    renderHook(() => useConvertQuoteToInvoiceMutation());

    act(() => queryMocks.onSuccess?.());

    expect(queryMocks.invalidateQueries).toHaveBeenCalledWith({ queryKey: ['quotes'] });
    expect(queryMocks.invalidateQueries).toHaveBeenCalledWith({ queryKey: ['invoices'] });
    expect(queryMocks.invalidateQueries).toHaveBeenCalledTimes(2);
  });
});
