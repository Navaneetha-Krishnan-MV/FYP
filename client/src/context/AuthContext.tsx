import { useCallback, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  AUTH_STORAGE_KEY,
  AuthContext,
  avatarFor,
  displayNameFor,
  readStoredUser,
} from './auth-context';
import type { AuthContextValue, AuthUser } from './auth-context';

export function AuthProvider({ children }: { children: ReactNode }) {
  // localStorage is synchronous, so the session is known on the very first render.
  const [user, setUser] = useState<AuthUser | null>(readStoredUser);

  const login = useCallback(async (email: string, password: string) => {
    const trimmed = email.trim().toLowerCase();

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      throw new Error('Enter a valid email address');
    }
    if (password.length < 4) {
      throw new Error('Password must be at least 4 characters');
    }

    const nextUser: AuthUser = {
      email: trimmed,
      name: displayNameFor(trimmed),
      avatarUrl: avatarFor(trimmed),
    };

    window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(nextUser));
    setUser(nextUser);
    return nextUser;
  }, []);

  const logout = useCallback(() => {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, isAuthenticated: user !== null, login, logout }),
    [user, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
