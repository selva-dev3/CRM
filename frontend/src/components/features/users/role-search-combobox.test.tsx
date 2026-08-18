import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { RoleSearchCombobox } from './role-search-combobox';

const roles = [
  { id: 'role-1', name: 'Sales Manager' },
  { id: 'role-2', name: 'Sales Executive' },
  { id: 'role-3', name: 'Support Agent' },
];

const useRolesQueryMock = vi.fn();

vi.mock('@/lib/api/roles', () => ({
  useRolesQuery: (...args: unknown[]) => useRolesQueryMock(...args),
}));

beforeEach(() => {
  useRolesQueryMock.mockReset();
  useRolesQueryMock.mockReturnValue({ data: roles, isLoading: false, isError: false, refetch: vi.fn() });
});

async function openPanel(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: /Search and select a role/ }));
}

describe('RoleSearchCombobox', () => {
  it('renders the placeholder when no role is selected', () => {
    render(<RoleSearchCombobox value="" onChange={vi.fn()} />);
    expect(screen.getByRole('button', { name: /Search and select a role/ })).toBeInTheDocument();
  });

  it('renders the selected role name', () => {
    render(<RoleSearchCombobox value="role-2" onChange={vi.fn()} />);
    expect(screen.getByRole('button', { name: /Sales Executive/ })).toBeInTheDocument();
  });

  it('opens and lists roles when clicked', async () => {
    const user = userEvent.setup();
    render(<RoleSearchCombobox value="" onChange={vi.fn()} />);
    await openPanel(user);

    expect(await screen.findByRole('option', { name: 'Sales Manager' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Sales Executive' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Support Agent' })).toBeInTheDocument();
  });

  it('shows a loading state while roles are being fetched', async () => {
    useRolesQueryMock.mockReturnValue({ data: [], isLoading: true, isError: false, refetch: vi.fn() });
    const user = userEvent.setup();
    render(<RoleSearchCombobox value="" onChange={vi.fn()} />);
    await openPanel(user);

    expect(screen.getByText('Searching roles...')).toBeInTheDocument();
  });

  it('shows an error state when role loading fails', async () => {
    useRolesQueryMock.mockReturnValue({ data: [], isLoading: false, isError: true, refetch: vi.fn() });
    const user = userEvent.setup();
    render(<RoleSearchCombobox value="" onChange={vi.fn()} />);
    await openPanel(user);

    expect(screen.getByText('Unable to load roles')).toBeInTheDocument();
  });

  it('retries loading roles from the error state', async () => {
    const refetchMock = vi.fn();
    useRolesQueryMock.mockReturnValue({ data: [], isLoading: false, isError: true, refetch: refetchMock });
    const user = userEvent.setup();
    render(<RoleSearchCombobox value="" onChange={vi.fn()} />);
    await openPanel(user);

    await user.click(screen.getByRole('button', { name: /Try again/ }));

    expect(refetchMock).toHaveBeenCalledTimes(1);
  });

  it('shows an empty state when no roles are returned', async () => {
    useRolesQueryMock.mockReturnValue({ data: [], isLoading: false, isError: false });
    const user = userEvent.setup();
    render(<RoleSearchCombobox value="" onChange={vi.fn()} />);
    await openPanel(user);

    expect(screen.getByText('No roles found')).toBeInTheDocument();
  });

  it('selects a role on click and calls onChange with its id', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<RoleSearchCombobox value="" onChange={onChange} />);
    await openPanel(user);

    await user.click(screen.getByRole('option', { name: 'Sales Executive' }));

    expect(onChange).toHaveBeenCalledWith('role-2');
  });

  it('closes the panel after selecting a role', async () => {
    const user = userEvent.setup();
    render(<RoleSearchCombobox value="" onChange={vi.fn()} />);
    await openPanel(user);
    await user.click(screen.getByRole('option', { name: 'Sales Manager' }));

    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  it('selects the highlighted role via keyboard navigation', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<RoleSearchCombobox value="" onChange={onChange} />);
    await openPanel(user);

    const input = screen.getByRole('combobox');
    input.focus();
    await user.keyboard('{ArrowDown}');
    await user.keyboard('{Enter}');

    expect(onChange).toHaveBeenCalledWith('role-2');
  });

  it('clamps the highlighted index when the roles list shrinks', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const { rerender } = render(<RoleSearchCombobox value="" onChange={onChange} />);
    await openPanel(user);

    const input = screen.getByRole('combobox');
    input.focus();
    await user.keyboard('{ArrowDown}');
    await user.keyboard('{ArrowDown}');

    useRolesQueryMock.mockReturnValue({ data: [roles[0]], isLoading: false, isError: false });
    rerender(<RoleSearchCombobox value="" onChange={onChange} />);

    await user.keyboard('{Enter}');
    expect(onChange).toHaveBeenCalledWith('role-1');
  });

  it('queries the backend with the debounced search term', async () => {
    const user = userEvent.setup();
    render(<RoleSearchCombobox value="" onChange={vi.fn()} />);
    await openPanel(user);

    const input = screen.getByRole('combobox');
    vi.useFakeTimers();
    fireEvent.change(input, { target: { value: 'Man' } });
    expect(useRolesQueryMock).toHaveBeenLastCalledWith(undefined);

    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(useRolesQueryMock).toHaveBeenLastCalledWith('Man');

    vi.useRealTimers();
  });
});
