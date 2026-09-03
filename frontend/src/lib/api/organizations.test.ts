import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  useQuery: vi.fn(),
}));

vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: mocks.get,
  },
}));

vi.mock('@tanstack/react-query', () => ({
  useQuery: mocks.useQuery,
  useMutation: vi.fn(),
  useQueryClient: vi.fn(),
}));

import { getCurrentOrganizationApi, useOrganizationByIdQuery } from './organizations';

describe('organization API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads the authenticated user current organization endpoint', async () => {
    mocks.get.mockResolvedValue({ id: 'org-current' });

    await getCurrentOrganizationApi();

    expect(mocks.get).toHaveBeenCalledWith('/organizations/current');
  });

  it('disables the by-id query when current organization mode opts out', () => {
    useOrganizationByIdQuery('', false);

    expect(mocks.useQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ['organization', ''],
        enabled: false,
      }),
    );
  });
});
