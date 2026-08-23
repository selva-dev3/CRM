/**
 * Centralized RBAC permission catalog for the frontend.
 *
 * Single source of truth for permission keys. Must stay in sync with the backend
 * catalog defined in `backend/app/services/role_service.py` (`ALL_STANDARD_PERMISSIONS`)
 * plus the `super_admin:manage` key inserted by migration `d1e2f3a4b5c6`.
 *
 * The backend resolves a user's effective keys via `AuthService.get_user_permissions`
 * (`backend/app/services/auth_service.py`): super admins (resolved role name in
 * `SUPER_ADMIN_ROLE_NAMES` or a DB role whose name matches) are granted every key,
 * every other user gets exactly the keys attached to their roles. The `"all"` legacy
 * sentinel is NOT emitted by the backend; the `hasPermission` helpers still honor it
 * so previously persisted sessions keep working.
 */

export const PERMISSIONS = {
  DASHBOARD: {
    READ: 'dashboard:read',
    CUSTOMIZE: 'dashboard:customize',
    EXPORT: 'dashboard:export',
  },
  LEADS: {
    READ: 'leads:read',
    CREATE: 'leads:create',
    UPDATE: 'leads:update',
    DELETE: 'leads:delete',
    EXPORT: 'leads:export',
    IMPORT: 'leads:import',
    ASSIGN: 'leads:assign',
    CONVERT: 'leads:convert',
    BULK_DELETE: 'leads:bulk_delete',
    BULK_UPDATE: 'leads:bulk_update',
  },
  CONTACTS: {
    READ: 'contacts:read',
    CREATE: 'contacts:create',
    UPDATE: 'contacts:update',
    DELETE: 'contacts:delete',
    EXPORT: 'contacts:export',
    IMPORT: 'contacts:import',
    ASSIGN: 'contacts:assign',
    BULK_DELETE: 'contacts:bulk_delete',
    BULK_UPDATE: 'contacts:bulk_update',
  },
  COMPANIES: {
    READ: 'companies:read',
    CREATE: 'companies:create',
    UPDATE: 'companies:update',
    DELETE: 'companies:delete',
    EXPORT: 'companies:export',
    IMPORT: 'companies:import',
    BULK_DELETE: 'companies:bulk_delete',
  },
  DEALS: {
    READ: 'deals:read',
    CREATE: 'deals:create',
    UPDATE: 'deals:update',
    DELETE: 'deals:delete',
    PIPELINE: 'deals:pipeline',
    EXPORT: 'deals:export',
    IMPORT: 'deals:import',
    ASSIGN: 'deals:assign',
    BULK_DELETE: 'deals:bulk_delete',
  },
  TASKS: {
    READ: 'tasks:read',
    CREATE: 'tasks:create',
    UPDATE: 'tasks:update',
    DELETE: 'tasks:delete',
    ASSIGN: 'tasks:assign',
    COMPLETE: 'tasks:complete',
  },
  MEETINGS: {
    READ: 'meetings:read',
    CREATE: 'meetings:create',
    UPDATE: 'meetings:update',
    DELETE: 'meetings:delete',
    INVITE: 'meetings:invite',
  },
  CALLS: {
    READ: 'calls:read',
    CREATE: 'calls:create',
    UPDATE: 'calls:update',
    DELETE: 'calls:delete',
    RECORDING: 'calls:recording',
  },
  EMAILS: {
    READ: 'emails:read',
    SEND: 'emails:send',
    TEMPLATES: 'emails:templates',
    DELETE: 'emails:delete',
  },
  NOTES: {
    READ: 'notes:read',
    CREATE: 'notes:create',
    UPDATE: 'notes:update',
    DELETE: 'notes:delete',
  },
  DOCUMENTS: {
    READ: 'documents:read',
    UPLOAD: 'documents:upload',
    DELETE: 'documents:delete',
    SHARE: 'documents:share',
  },
  PRODUCTS: {
    READ: 'products:read',
    CREATE: 'products:create',
    UPDATE: 'products:update',
    DELETE: 'products:delete',
    EXPORT: 'products:export',
    IMPORT: 'products:import',
  },
  QUOTES: {
    READ: 'quotes:read',
    CREATE: 'quotes:create',
    UPDATE: 'quotes:update',
    APPROVE: 'quotes:approve',
    DELETE: 'quotes:delete',
    SEND: 'quotes:send',
  },
  INVOICES: {
    READ: 'invoices:read',
    CREATE: 'invoices:create',
    UPDATE: 'invoices:update',
    SEND: 'invoices:send',
    DELETE: 'invoices:delete',
    PAYMENT: 'invoices:payment',
  },
  REPORTS: {
    READ: 'reports:read',
    CREATE: 'reports:create',
    EXPORT: 'reports:export',
    SCHEDULE: 'reports:schedule',
  },
  CALENDAR: {
    READ: 'calendar:read',
    WRITE: 'calendar:write',
    SYNC: 'calendar:sync',
  },
  USERS: {
    READ: 'users:read',
    CREATE: 'users:create',
    INVITE: 'users:invite',
    UPDATE: 'users:update',
    DELETE: 'users:delete',
    EXPORT: 'users:export',
    IMPORT: 'users:import',
    ROLES: 'users:roles',
  },
  ROLES: {
    READ: 'roles:read',
    CREATE: 'roles:create',
    UPDATE: 'roles:update',
    DELETE: 'roles:delete',
    ASSIGN: 'roles:assign',
  },
  ORGANIZATION: {
    READ: 'organization:read',
    UPDATE: 'organization:update',
    BILLING: 'organization:billing',
    DOMAINS: 'organization:domains',
    BRANDING: 'organization:branding',
    AUDIT: 'organization:audit',
  },
  INVITATIONS: {
    READ: 'invitations:read',
    CREATE: 'invitations:create',
    RESEND: 'invitations:resend',
    REVOKE: 'invitations:revoke',
  },
  INTEGRATIONS: {
    READ: 'integrations:read',
    MANAGE: 'integrations:manage',
    APIKEYS: 'integrations:apikeys',
  },
  NOTIFICATIONS: {
    READ: 'notifications:read',
    MANAGE: 'notifications:manage',
    SEND: 'notifications:send',
  },
  SETTINGS: {
    READ: 'settings:read',
    UPDATE: 'settings:update',
    SECURITY: 'settings:security',
  },
  ACTIVITIES: {
    READ: 'activities:read',
    CREATE: 'activities:create',
    EXPORT: 'activities:export',
  },
  AI: {
    READ: 'ai:read',
    GENERATE: 'ai:generate',
  },
  SUPER_ADMIN: {
    MANAGE: 'super_admin:manage',
  },
} as const;

export type PermissionKey = {
  [K in keyof typeof PERMISSIONS]: (typeof PERMISSIONS)[K][keyof (typeof PERMISSIONS)[K]];
}[keyof typeof PERMISSIONS];

const LEGACY_ALL_SENTINEL = 'all';

/**
 * Returns true when `required` is missing (nothing required -> allowed),
 * the permission list is empty (deny), the list contains the legacy `all`
 * sentinel (wildcard), or the exact key is present.
 */
export function hasPermission(permissions: readonly string[] | undefined, required?: PermissionKey): boolean {
  if (!required) return true;
  if (!permissions || permissions.length === 0) return false;
  if (permissions.includes(LEGACY_ALL_SENTINEL)) return true;
  return permissions.includes(required);
}

/** Returns true when the user holds at least one of the required permissions. */
export function hasAnyPermission(permissions: readonly string[] | undefined, required: readonly PermissionKey[]): boolean {
  if (!required || required.length === 0) return true;
  return required.some((permission) => hasPermission(permissions, permission));
}

/** Returns true when the user holds every one of the required permissions. */
export function hasAllPermissions(permissions: readonly string[] | undefined, required: readonly PermissionKey[]): boolean {
  if (!required || required.length === 0) return true;
  return required.every((permission) => hasPermission(permissions, permission));
}