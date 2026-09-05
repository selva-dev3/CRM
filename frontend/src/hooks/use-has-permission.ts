'use client';

import { useCallback, useEffect, useState } from 'react';
import { hasPermission, hasAnyPermission, hasAllPermissions, PermissionKey } from '@/lib/permissions';
import { useOptionalAuth } from '@/providers/auth-provider';

/**
 * Event name dispatched whenever the persisted user (and therefore the user's
 * permission set) changes in the current tab, e.g. after login, invitation
 * acceptance, or logout. Listeners re-read the stored user immediately.
 */
export const AUTH_USER_CHANGED_EVENT = 'auth:user-changed';

/** Read the stored user's permissions from localStorage/sessionStorage. */
function getStoredPermissions(): readonly string[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = sessionStorage.getItem('user') || localStorage.getItem('user');
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed?.permissions) ? parsed.permissions : [];
  } catch {
    return [];
  }
}

/** Dispatches an event so every mounted permission consumer re-reads the stored user. */
export function notifyAuthUserChanged(): void {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(AUTH_USER_CHANGED_EVENT));
  }
}

/**
 * Reactive permission hook. The permission set is loaded from the persisted user
 * object and stays in sync with:
 *  - login / logout / invitation acceptance in the same tab (custom event)
 *  - user changes in another tab (`storage` event)
 */
export function useHasPermission() {
  const auth = useOptionalAuth();
  const [permissions, setPermissions] = useState<readonly string[]>(getStoredPermissions);

  useEffect(() => {
    const refresh = () => setPermissions(getStoredPermissions());
    window.addEventListener('storage', refresh);
    window.addEventListener(AUTH_USER_CHANGED_EVENT, refresh);
    return () => {
      window.removeEventListener('storage', refresh);
      window.removeEventListener(AUTH_USER_CHANGED_EVENT, refresh);
    };
  }, []);

  const effectivePermissions = auth?.user?.permissions ?? permissions;

  return {
    permissions: effectivePermissions,
    hasPermission: useCallback((required?: PermissionKey) => hasPermission(effectivePermissions, required), [effectivePermissions]),
    hasAnyPermission: useCallback(
      (required: readonly PermissionKey[]) => hasAnyPermission(effectivePermissions, required),
      [effectivePermissions]
    ),
    hasAllPermissions: useCallback(
      (required: readonly PermissionKey[]) => hasAllPermissions(effectivePermissions, required),
      [effectivePermissions]
    ),
  };
}
