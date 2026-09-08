'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { getCurrentUserApi, logoutApi, type CurrentUserResponse } from '@/lib/api/auth';
import { ApiError, invalidateAuthSession, markAuthSessionActive } from '@/lib/api/client';
import { getOrganizationContext, setOrganizationContext, ORGANIZATION_DELETED_EVENT, ORGANIZATION_DELETED_BROADCAST } from '@/lib/organization-context';
import {
  AUTH_SESSION_BROADCAST_KEY,
  AUTH_SESSION_CHANGED_EVENT,
  clearStoredSession,
  parseAuthBroadcast,
  persistSessionUser,
  readStoredUser,
} from '@/lib/auth-session';

type AuthStatus = 'unknown' | 'authenticated' | 'unauthenticated';

interface AuthContextValue {
  status: AuthStatus;
  user: CurrentUserResponse | null;
  setSession: (user: CurrentUserResponse, remember?: boolean) => void;
  verifySession: () => Promise<CurrentUserResponse>;
  logout: () => Promise<void>;
  isLoggingOut: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<CurrentUserResponse | null>(readStoredUser);
  const [status, setStatus] = useState<AuthStatus>('unknown');
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const isLoggingOutRef = useRef(false);
  const authGenerationRef = useRef(0);
  const logoutPromiseRef = useRef<Promise<void> | null>(null);

  const resetLocalSession = useCallback(
    (broadcast = true) => {
      clearStoredSession({ broadcast });
      setOrganizationContext(null);
      setUser(null);
      setStatus('unauthenticated');
      void queryClient.cancelQueries();
      queryClient.clear();
    },
    [queryClient],
  );

  const setSession = useCallback((nextUser: CurrentUserResponse, remember?: boolean) => {
    setOrganizationContext(null);
    markAuthSessionActive();
    authGenerationRef.current += 1;
    persistSessionUser(nextUser, { remember });
    setUser(nextUser);
    setStatus('authenticated');
  }, []);

  const verifySession = useCallback(async () => {
    const requestGeneration = authGenerationRef.current;
    try {
      const currentUser = await getCurrentUserApi();
      if (requestGeneration !== authGenerationRef.current || isLoggingOutRef.current) {
        throw new Error('Session verification was superseded by logout');
      }
      markAuthSessionActive();
      persistSessionUser(currentUser, { broadcast: false });
      setUser(currentUser);
      setStatus('authenticated');
      return currentUser;
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        setStatus('unauthenticated');
      }
      throw error;
    }
  }, []);

  const refreshAuthorization = useCallback(async () => {
    const currentUser = await verifySession();
    await queryClient.cancelQueries();
    queryClient.clear();
    return currentUser;
  }, [queryClient, verifySession]);

  const logout = useCallback(async () => {
    if (logoutPromiseRef.current) return logoutPromiseRef.current;

    invalidateAuthSession();
    authGenerationRef.current += 1;
    isLoggingOutRef.current = true;
    setIsLoggingOut(true);
    const logoutPromise = (async () => {
      try {
        await logoutApi();
        resetLocalSession(true);
      } catch (error) {
        // Clear local state to stop UI use, but propagate the failure so callers
        // cannot report a successful server logout when revocation was unknown.
        resetLocalSession(true);
        throw error;
      } finally {
        isLoggingOutRef.current = false;
        setIsLoggingOut(false);
      }
    })();
    logoutPromiseRef.current = logoutPromise.finally(() => {
      logoutPromiseRef.current = null;
    });
    return logoutPromiseRef.current;
  }, [resetLocalSession]);

  useEffect(() => {
    const recoverOrganization = () => {
      void queryClient.cancelQueries();
      queryClient.clear();
      setOrganizationContext(null);
      if (user?.is_platform_admin) window.location.assign('/organization');
      else { resetLocalSession(false); window.location.assign('/login'); }
    };
    const unavailableOrganization = (event: Event) => {
      const requestedOrganization: unknown = (event as CustomEvent).detail;
      if (typeof requestedOrganization === 'string' && requestedOrganization !== getOrganizationContext()) return;
      recoverOrganization();
    };
    const deletedOrganization = (organizationId: string) => {
      void queryClient.invalidateQueries({ queryKey: ['platform-organizations'] });
      if (getOrganizationContext() === organizationId || (!user?.is_platform_admin && user?.organization_id === organizationId)) {
        recoverOrganization();

      }
    };
    const handleOrganizationDeleted = (event: Event) => {
      const organizationId: unknown = (event as CustomEvent).detail;
      if (typeof organizationId === 'string') deletedOrganization(organizationId);
    };
    const handleSessionEvent = (event: Event) => {
      const action = (event as CustomEvent<{ action?: string }>).detail?.action;
      if (action === 'logout') {
        invalidateAuthSession();
        authGenerationRef.current += 1;
        resetLocalSession(false);
      }
      if (action === 'login') {
        const storedUser = readStoredUser();
        if (storedUser) {
          setOrganizationContext(null);
          queryClient.clear();
          markAuthSessionActive();
          authGenerationRef.current += 1;
          setUser(storedUser);
          setStatus('authenticated');
        }
      }
      if (action === 'refresh') {
        void refreshAuthorization().catch(() => resetLocalSession(false));
      }
    };
    const handleStorage = (event: StorageEvent) => {
      if (event.key === ORGANIZATION_DELETED_BROADCAST && event.newValue) {
        try {
          const payload: unknown = JSON.parse(event.newValue);
          if (payload && typeof payload === 'object' && 'organizationId' in payload && typeof payload.organizationId === 'string') {
            deletedOrganization(payload.organizationId);
          }
        } catch { /* Ignore malformed cross-tab notifications; the API enforces access. */ }
        return;
      }
      if (event.key !== AUTH_SESSION_BROADCAST_KEY) return;
      const action = parseAuthBroadcast(event.newValue);
      if (action === 'logout') {
        invalidateAuthSession();
        authGenerationRef.current += 1;
        resetLocalSession(false);
      } else if (action === 'login') {
        setOrganizationContext(null);
        queryClient.clear();
        void verifySession().catch(() => resetLocalSession(false));
      } else if (action === 'refresh') {
        void refreshAuthorization().catch(() => resetLocalSession(false));
      }
    };
    const handleUnauthorized = () => {
      invalidateAuthSession();
      authGenerationRef.current += 1;
      resetLocalSession(false);
    };

    window.addEventListener(AUTH_SESSION_CHANGED_EVENT, handleSessionEvent);
    window.addEventListener('storage', handleStorage);
    window.addEventListener('auth:unauthorized', handleUnauthorized);
    window.addEventListener('organization:unavailable', unavailableOrganization);
    window.addEventListener(ORGANIZATION_DELETED_EVENT, handleOrganizationDeleted);
    return () => {
      window.removeEventListener(AUTH_SESSION_CHANGED_EVENT, handleSessionEvent);
      window.removeEventListener('storage', handleStorage);
      window.removeEventListener('auth:unauthorized', handleUnauthorized);
      window.removeEventListener('organization:unavailable', unavailableOrganization);
      window.removeEventListener(ORGANIZATION_DELETED_EVENT, handleOrganizationDeleted);
    };
  }, [queryClient, refreshAuthorization, resetLocalSession, verifySession, user]);

  const value = useMemo(
    () => ({ status, user, setSession, verifySession, logout, isLoggingOut }),
    [isLoggingOut, logout, setSession, status, user, verifySession],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}

export function useOptionalAuth(): AuthContextValue | null {
  return useContext(AuthContext);
}
