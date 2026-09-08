import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RoleDetailPage from './page';

const state = vi.hoisted(() => ({
  permissions: new Set(['roles:read']),
  system: false,
  can: (permission?: string): boolean => !permission || state.permissions.has(permission),
}));
vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'role-1' }),
  useRouter: () => ({ push: vi.fn() }),
}));
vi.mock('@/hooks/use-has-permission', () => ({
  useHasPermission: () => ({ hasPermission: state.can }),
}));
vi.mock('@/lib/api/roles', () => {
  const mutation = () => ({ mutateAsync: vi.fn(), isPending: false });
  return {
    useRoleQuery: () => ({ data: {
      id: 'role-1', name: 'Custom Sales', permissions: ['leads:read'],
      is_system_role: state.system, user_count: 0,
    } }),
    useDefaultRoleQuery: () => ({ data: null }),
    usePermissionMatrixQuery: () => ({ data: [
      { id: 'permission-1', key: 'leads:read', name: 'Read leads', category: 'Leads' },
    ] }),
    useRoleUsersQuery: () => ({ data: [] }),
    useCloneRoleMutation: mutation,
    useAssignPermissionsMutation: mutation,
    useRemovePermissionMutation: mutation,
    useAssignRoleToUserMutation: mutation,
    useSetDefaultRoleMutation: mutation,
    useDeleteRoleMutation: mutation,
    checkPermissionApi: vi.fn(),
  };
});

describe('Role detail permission controls', () => {
  beforeEach(() => {
    state.permissions = new Set(['roles:read']);
    state.system = false;
  });

  it('hides removal and selection from read-only viewers', () => {
    render(<RoleDetailPage />);
    expect(screen.getByText('Read leads')).toBeInTheDocument();
    expect(screen.queryByTitle('Remove permission from role')).not.toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  });

  it('allows selection and removal with roles:assign', () => {
    state.permissions.add('roles:assign');
    render(<RoleDetailPage />);
    expect(screen.getByTitle('Remove permission from role')).toBeInTheDocument();
    expect(screen.getAllByRole('checkbox').length).toBeGreaterThan(0);
  });

  it('keeps system-role permissions protected even with roles:assign', () => {
    state.permissions.add('roles:assign');
    state.system = true;
    render(<RoleDetailPage />);
    expect(screen.queryByTitle('Remove permission from role')).not.toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    expect(screen.getByText('Protected')).toBeInTheDocument();
  });
});
