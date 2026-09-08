import type { CurrentUserResponse } from '@/lib/api/auth';

export const AUTH_SESSION_CHANGED_EVENT = 'auth:session-changed';
export const AUTH_SESSION_BROADCAST_KEY = 'crm:auth-event';

export type AuthSessionAction = 'login' | 'logout' | 'refresh';

export function readStoredUser(): CurrentUserResponse | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem('user') || localStorage.getItem('user');
    return raw ? (JSON.parse(raw) as CurrentUserResponse) : null;
  } catch {
    return null;
  }
}

function announceSessionChange(action: AuthSessionAction): void {
  window.dispatchEvent(new CustomEvent(AUTH_SESSION_CHANGED_EVENT, { detail: { action } }));
  localStorage.setItem(
    AUTH_SESSION_BROADCAST_KEY,
    JSON.stringify({ action, timestamp: Date.now() }),
  );
}

export function persistSessionUser(
  user: CurrentUserResponse,
  options: { remember?: boolean; broadcast?: boolean } = {},
): void {
  if (typeof window === 'undefined') return;
  const serialized = JSON.stringify(user);
  sessionStorage.setItem('user', serialized);
  if (options.remember === true || (options.remember === undefined && localStorage.getItem('user') !== null)) {
    localStorage.setItem('user', serialized);
  } else if (options.remember === false) {
    localStorage.removeItem('user');
  }
  if (options.broadcast !== false) announceSessionChange('login');
}

export function clearStoredSession(options: { broadcast?: boolean } = {}): void {
  if (typeof window === 'undefined') return;
  const storedUser = readStoredUser();
  if (storedUser?.id) {
    const userPrefixes = [
      `pending-invoice-payment:${storedUser.id}:`,
      `subscription-checkout:${storedUser.id}:`,
    ];
    const pendingKeys = Array.from({ length: sessionStorage.length }, (_, index) => sessionStorage.key(index))
      .filter((key): key is string => key !== null)
      .filter((key) => userPrefixes.some((prefix) => key.startsWith(prefix)));
    pendingKeys.forEach((key) => sessionStorage.removeItem(key));
  }
  sessionStorage.removeItem('token');
  localStorage.removeItem('token');
  sessionStorage.removeItem('user');
  localStorage.removeItem('user');
  if (options.broadcast !== false) announceSessionChange('logout');
}

export function notifyPermissionsInvalidated(): void {
  if (typeof window !== 'undefined') announceSessionChange('refresh');
}

export function parseAuthBroadcast(value: string | null): AuthSessionAction | null {
  if (!value) return null;
  try {
    const action = JSON.parse(value)?.action;
    return action === 'login' || action === 'logout' || action === 'refresh' ? action : null;
  } catch {
    return null;
  }
}
