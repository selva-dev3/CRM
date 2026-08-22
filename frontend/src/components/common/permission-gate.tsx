'use client';

import React from 'react';
import { useHasPermission } from '@/hooks/use-has-permission';
import { PermissionKey } from '@/lib/permissions';

interface PermissionGateProps {
  readonly permission?: PermissionKey;
  readonly children: React.ReactNode;
}

export function PermissionGate({ permission, children }: PermissionGateProps): React.JSX.Element | null {
  const { hasPermission } = useHasPermission();
  if (!hasPermission(permission)) return null;
  return <>{children}</>;
}
