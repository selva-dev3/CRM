import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { PermissionGate } from './permission-gate';
import { AUTH_USER_CHANGED_EVENT } from '@/hooks/use-has-permission';
import { PERMISSIONS } from '@/lib/permissions';

function setStoredUser(permissions: string[]): void {
  window.localStorage.setItem('user', JSON.stringify({ role: 'member', email: 'member@company.com', permissions }));
}

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
});

describe('PermissionGate', () => {
  it('renders children when the required permission is held', () => {
    setStoredUser([PERMISSIONS.LEADS.READ]);
    render(
      <PermissionGate permission={PERMISSIONS.LEADS.READ}>
        <span>Add Lead</span>
      </PermissionGate>
    );
    expect(screen.getByText('Add Lead')).toBeInTheDocument();
  });

  it('renders nothing when the required permission is missing', () => {
    setStoredUser([PERMISSIONS.CONTACTS.READ]);
    render(
      <PermissionGate permission={PERMISSIONS.LEADS.READ}>
        <span>Add Lead</span>
      </PermissionGate>
    );
    expect(screen.queryByText('Add Lead')).not.toBeInTheDocument();
  });

  it('renders nothing when no persisted user exists', () => {
    render(
      <PermissionGate permission={PERMISSIONS.LEADS.READ}>
        <span>Add Lead</span>
      </PermissionGate>
    );
    expect(screen.queryByText('Add Lead')).not.toBeInTheDocument();
  });

  it('renders children when the gate has no permission requirement', () => {
    render(
      <PermissionGate>
        <span>Always Visible</span>
      </PermissionGate>
    );
    expect(screen.getByText('Always Visible')).toBeInTheDocument();
  });

  it('re-renders reactively when the persisted permissions change (no manual refresh / no flicker)', () => {
    setStoredUser([]);
    render(
      <PermissionGate permission={PERMISSIONS.LEADS.READ}>
        <span>Add Lead</span>
      </PermissionGate>
    );
    expect(screen.queryByText('Add Lead')).not.toBeInTheDocument();

    act(() => {
      setStoredUser([PERMISSIONS.LEADS.READ]);
      window.dispatchEvent(new Event(AUTH_USER_CHANGED_EVENT));
    });

    expect(screen.getByText('Add Lead')).toBeInTheDocument();
  });
});
