'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { getCurrentUserApi, logoutApi, type CurrentUserResponse } from '@/lib/api/auth';
import { invalidateAuthSession, markAuthSessionActive } from '@/lib/api/client';
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
      setUser(null);
      setStatus('unauthenticated');
      void queryClient.cancelQueries();
      queryClient.clear();
    },
    [queryClient],
  );

  const setSession = useCallback((nextUser: CurrentUserResponse, remember?: boolean) => {
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
      setStatus('unauthenticated');
      throw error;
    }
  }, []);

  const logout = useCallback(async () => {
    if (logoutPromiseRef.current) return logoutPromiseRef.current;

    invalidateAuthSession();
    authGenerationRef.current += 1;
    isLoggingOutRef.current = true;
    setIsLoggingOut(true);
    resetLocalSession(true);

    const logoutPromise = (async () => {
      try {
        await logoutApi();
      } catch (error) {
        // Local logout is authoritative even when the server cannot be reached.
        console.error('Backend logout failed after local logout completed', error);
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
          markAuthSessionActive();
          authGenerationRef.current += 1;
          setUser(storedUser);
          setStatus('authenticated');
        }
      }
    };
    const handleStorage = (event: StorageEvent) => {
      if (event.key !== AUTH_SESSION_BROADCAST_KEY) return;
      const action = parseAuthBroadcast(event.newValue);
      if (action === 'logout') {
        invalidateAuthSession();
        authGenerationRef.current += 1;
        resetLocalSession(false);
      } else if (action === 'login') {
        void verifySession().catch(() => resetLocalSession(false));
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
    return () => {
      window.removeEventListener(AUTH_SESSION_CHANGED_EVENT, handleSessionEvent);
      window.removeEventListener('storage', handleStorage);
      window.removeEventListener('auth:unauthorized', handleUnauthorized);
    };
  }, [resetLocalSession, verifySession]);

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
