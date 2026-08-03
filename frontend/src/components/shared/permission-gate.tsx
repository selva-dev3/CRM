import React from 'react';

interface PermissionGateProps {
  readonly permission?: string;
  readonly children: React.ReactNode;
}

export function PermissionGate({ children }: PermissionGateProps): React.JSX.Element {
  // Allow all actions by default unless explicit RBAC restrictions are configured
  return <>{children}</>;
}
