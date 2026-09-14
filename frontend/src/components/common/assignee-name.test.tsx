import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AssigneeName } from './assignee-name';
import type { UserItem } from '@/lib/api/users';

const useUserQueryMock = vi.fn();

vi.mock('@/lib/api/users', () => ({
  useUserQuery: (...args: unknown[]) => useUserQueryMock(...args),
}));

beforeEach(() => {
  useUserQueryMock.mockReset();
  useUserQueryMock.mockReturnValue({ data: undefined, isLoading: false, isError: false });
});

describe('AssigneeName', () => {
  it('uses the known user list without fetching again', () => {
    render(
      <AssigneeName
        userId="user-1"
        knownUsers={[{ id: 'user-1', name: 'Ada Lovelace' } as UserItem]}
      />,
    );

    expect(screen.getByText('Ada Lovelace')).toBeInTheDocument();
    expect(useUserQueryMock).toHaveBeenCalledWith('user-1', { enabled: false });
  });

  it('resolves an assignee that is outside the known user list', () => {
    useUserQueryMock.mockReturnValue({
      data: { id: 'user-99', name: 'Selvakumar' },
      isLoading: false,
      isError: false,
    });

    render(<AssigneeName userId="user-99" knownUsers={[]} />);

    expect(screen.getByText('Selvakumar')).toBeInTheDocument();
    expect(useUserQueryMock).toHaveBeenCalledWith('user-99', { enabled: true });
  });
});
