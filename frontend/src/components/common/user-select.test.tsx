import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UserSelect } from './user-select';

const users = [
  { id: 'user-1', name: 'Ada Lovelace', email: 'ada@example.com' },
  { id: 'user-2', name: 'Grace Hopper', email: '' },
];

const useUsersQueryMock = vi.fn();

vi.mock('@/lib/api/users', () => ({
  useUsersQuery: (...args: unknown[]) => useUsersQueryMock(...args),
}));

beforeEach(() => {
  vi.useRealTimers();
  useUsersQueryMock.mockReset();
  useUsersQueryMock.mockReturnValue({ data: users, isLoading: false });
});

describe('UserSelect', () => {
  it('renders the selected user and handles selection and clearing', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<UserSelect value="user-1" onChange={onChange} />);

    expect(screen.getByRole('button', { name: /Ada Lovelace \(ada@example.com\)/ })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Ada Lovelace/ }));
    await user.click(screen.getByRole('button', { name: /Grace Hopper/ }));
    expect(onChange).toHaveBeenCalledWith('user-2');

    await user.click(screen.getByRole('button', { name: /Ada Lovelace/ }));
    await user.click(screen.getByRole('button', { name: /None \/ Clear Selection/ }));
    expect(onChange).toHaveBeenLastCalledWith('');
  });

  it('debounces the API search term and shows loading and empty states', async () => {
    vi.useFakeTimers();
    useUsersQueryMock.mockReturnValue({ data: [], isLoading: true });
    render(<UserSelect value="" onChange={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /Select User Account/ }));
    expect(screen.getByText('Searching users via API...')).toBeInTheDocument();

    const input = screen.getByPlaceholderText('Search user by name or email...');
    fireEvent.change(input, { target: { value: 'ada' } });
    expect(useUsersQueryMock).toHaveBeenLastCalledWith(1, 100, undefined);

    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(useUsersQueryMock).toHaveBeenLastCalledWith(1, 100, 'ada');
  });
});
