import type { CurrentUserResponse } from '@/lib/api/auth';

export const AUTH_SESSION_CHANGED_EVENT = 'auth:session-changed';
export const AUTH_SESSION_BROADCAST_KEY = 'crm:auth-event';
export const AUTH_ACCESS_TOKEN_KEY = 'access_token';

export type AuthSessionAction = 'login' | 'logout' | 'refresh';

function getBrowserStorage(): Storage | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function isStructurallyUsableAccessToken(token: string): boolean {
  const parts = token.split('.');
  if (parts.length !== 3 || parts.some((part) => part.length === 0)) return false;
  try {
    const encodedPayload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const paddedPayload = encodedPayload.padEnd(encodedPayload.length + ((4 - encodedPayload.length % 4) % 4), '=');
    const payload = JSON.parse(atob(paddedPayload));
    return typeof payload === 'object' && payload !== null && typeof payload.exp === 'number';
  } catch {
    return false;
  }
}

export function getAccessToken(): string | null {
  const storage = getBrowserStorage();
  if (!storage) return null;
  try {
    const token = storage.getItem(AUTH_ACCESS_TOKEN_KEY)?.trim() || null;
    if (token && !isStructurallyUsableAccessToken(token)) {
      storage.removeItem(AUTH_ACCESS_TOKEN_KEY);
      return null;
    }
    return token;
  } catch {
    return null;
  }
}

export function setAccessToken(token: string): boolean {
  const storage = getBrowserStorage();
  const normalized = token.trim();
  if (!storage || !normalized || !isStructurallyUsableAccessToken(normalized)) return false;
  try {
    storage.setItem(AUTH_ACCESS_TOKEN_KEY, normalized);
    return storage.getItem(AUTH_ACCESS_TOKEN_KEY) === normalized;
  } catch {
    return false;
  }
}

export function clearAccessToken(): void {
  const storage = getBrowserStorage();
  try {
    storage?.removeItem(AUTH_ACCESS_TOKEN_KEY);
  } catch {
    // Storage may be unavailable or blocked by browser privacy settings.
  }
}

export function hasAccessToken(): boolean {
  return getAccessToken() !== null;
}

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
  try {
    localStorage.setItem(
      AUTH_SESSION_BROADCAST_KEY,
      JSON.stringify({ action, timestamp: Date.now() }),
    );
  } catch {
    // Cross-tab notification is best effort when browser storage is blocked.
  }
}

export function persistSessionUser(
  user: CurrentUserResponse,
  options: { remember?: boolean; broadcast?: boolean } = {},
): void {
  if (typeof window === 'undefined') return;
  try {
    const serialized = JSON.stringify(user);
    sessionStorage.setItem('user', serialized);
    if (options.remember === true || (options.remember === undefined && localStorage.getItem('user') !== null)) {
      localStorage.setItem('user', serialized);
    } else if (options.remember === false) {
      localStorage.removeItem('user');
    }
  } catch {
    // User metadata is optional; the access token remains the credential.
  }
  if (options.broadcast !== false) announceSessionChange('login');
}

export function clearStoredSession(options: { broadcast?: boolean } = {}): void {
  if (typeof window === 'undefined') return;
  try {
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
    clearAccessToken();
    sessionStorage.removeItem('token');
    localStorage.removeItem('token');
    sessionStorage.removeItem('user');
    localStorage.removeItem('user');
  } catch {
    clearAccessToken();
  }
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
