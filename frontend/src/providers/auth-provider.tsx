'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { getCurrentUserApi, logoutApi, type CurrentUserResponse } from '@/lib/api/auth';
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
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<CurrentUserResponse | null>(readStoredUser);
  const [status, setStatus] = useState<AuthStatus>('unknown');

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
    persistSessionUser(nextUser, { remember });
    setUser(nextUser);
    setStatus('authenticated');
  }, []);

  const verifySession = useCallback(async () => {
    try {
      const currentUser = await getCurrentUserApi();
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
    await logoutApi();
    resetLocalSession(true);
  }, [resetLocalSession]);

  useEffect(() => {
    const handleSessionEvent = (event: Event) => {
      const action = (event as CustomEvent<{ action?: string }>).detail?.action;
      if (action === 'logout') resetLocalSession(false);
      if (action === 'login') {
        const storedUser = readStoredUser();
        if (storedUser) {
          setUser(storedUser);
          setStatus('authenticated');
        }
      }
    };
    const handleStorage = (event: StorageEvent) => {
      if (event.key !== AUTH_SESSION_BROADCAST_KEY) return;
      const action = parseAuthBroadcast(event.newValue);
      if (action === 'logout') {
        resetLocalSession(false);
      } else if (action === 'login') {
        void verifySession().catch(() => resetLocalSession(false));
      }
    };
    const handleUnauthorized = () => resetLocalSession(false);

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
    () => ({ status, user, setSession, verifySession, logout }),
    [logout, setSession, status, user, verifySession],
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
