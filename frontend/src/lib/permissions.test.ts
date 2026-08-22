import { describe, expect, it } from 'vitest';
import { hasAllPermissions, hasAnyPermission, hasPermission, PERMISSIONS, type PermissionKey } from './permissions';

const allKeys = Object.values(PERMISSIONS).flatMap((group) => Object.values(group));

describe('hasPermission', () => {
  it('allows access when no permission is required', () => {
    expect(hasPermission(['leads:read'], undefined)).toBe(true);
    expect(hasPermission([], undefined)).toBe(true);
    expect(hasPermission(undefined, undefined)).toBe(true);
  });

  it('denies access when the permission list is missing or empty', () => {
    expect(hasPermission(undefined, PERMISSIONS.LEADS.READ)).toBe(false);
    expect(hasPermission([], PERMISSIONS.LEADS.READ)).toBe(false);
  });

  it('grants access when the exact key is present', () => {
    expect(hasPermission([PERMISSIONS.LEADS.READ], PERMISSIONS.LEADS.READ)).toBe(true);
  });

  it('denies access when the exact key is absent', () => {
    expect(hasPermission([PERMISSIONS.CONTACTS.READ], PERMISSIONS.LEADS.READ)).toBe(false);
  });

  it('honors the legacy "all" sentinel for previously persisted sessions', () => {
    expect(hasPermission(['all'], PERMISSIONS.SUPER_ADMIN.MANAGE)).toBe(true);
  });
});

describe('hasAnyPermission', () => {
  it('allows access when no permissions are required', () => {
    expect(hasAnyPermission(undefined, [])).toBe(true);
  });

  it('grants access when at least one required key is held', () => {
    expect(hasAnyPermission([PERMISSIONS.LEADS.READ], [PERMISSIONS.CONTACTS.READ, PERMISSIONS.LEADS.READ])).toBe(true);
  });

  it('denies access when none of the required keys are held', () => {
    expect(hasAnyPermission([PERMISSIONS.LEADS.READ], [PERMISSIONS.CONTACTS.READ, PERMISSIONS.DEALS.READ])).toBe(false);
  });
});

describe('hasAllPermissions', () => {
  it('allows access when no permissions are required', () => {
    expect(hasAllPermissions(undefined, [])).toBe(true);
  });

  it('grants access when every required key is held', () => {
    expect(
      hasAllPermissions(
        [PERMISSIONS.LEADS.READ, PERMISSIONS.LEADS.UPDATE],
        [PERMISSIONS.LEADS.READ, PERMISSIONS.LEADS.UPDATE]
      )
    ).toBe(true);
  });

  it('denies access when any required key is missing', () => {
    expect(
      hasAllPermissions([PERMISSIONS.LEADS.READ], [PERMISSIONS.LEADS.READ, PERMISSIONS.LEADS.UPDATE])
    ).toBe(false);
  });
});

describe('PERMISSIONS catalog', () => {
  it('exposes the real backend keys referenced by the UI', () => {
    expect(PERMISSIONS.ORGANIZATION.READ).toBe('organization:read');
    expect(PERMISSIONS.INTEGRATIONS.READ).toBe('integrations:read');
    expect(PERMISSIONS.USERS.READ).toBe('users:read');
    expect(PERMISSIONS.ROLES.READ).toBe('roles:read');
    expect(PERMISSIONS.NOTIFICATIONS.READ).toBe('notifications:read');
  });

  it('includes users:create because the backend router enforces it', () => {
    expect(PERMISSIONS.USERS.CREATE).toBe('users:create');
    expect(allKeys).toContain('users:create');
  });

  it('does not contain the non-existent key from the original task spec', () => {
    expect(allKeys).not.toContain('organizations:list');
  });

  it('is exhaustive enough for a superadmin grant (every key usable)', () => {
    expect(allKeys.length).toBeGreaterThan(100);
    for (const key of allKeys) {
      expect(hasPermission(allKeys, key as PermissionKey)).toBe(true);
    }
  });
});
