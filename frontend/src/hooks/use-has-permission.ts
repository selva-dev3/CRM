'use client';

import { useMemo } from 'react';
import { hasPermission } from '@/lib/utils';

function getStoredPermissions(): string[] | undefined {
  if (typeof window === 'undefined') return undefined;
  try {
    const raw = localStorage.getItem('user') || sessionStorage.getItem('user');
    if (!raw) return undefined;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed?.permissions) ? parsed.permissions : undefined;
  } catch {
    return undefined;
  }
}

export function useHasPermission() {
  const permissions = useMemo(() => getStoredPermissions(), []);

  return {
    permissions,
    hasPermission: (required?: string): boolean => hasPermission(permissions, required),
  };
}
