import { createContext } from 'react';

export interface AuthUser {
  name: string;
  email: string;
  avatarUrl: string;
}

export interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<AuthUser>;
  logout: () => void;
}

/**
 * The Express API has no auth endpoints — every route resolves the actor through
 * `getOrCreateDefaultUser()`. This context is therefore a client-side session
 * gate for the demo: it keeps the workspace behind a login screen and gives the
 * shell a real identity to render, without pretending to be a security boundary.
 */
export const AuthContext = createContext<AuthContextValue | null>(null);

export const AUTH_STORAGE_KEY = 'codelens.session';

export function avatarFor(email: string): string {
  return `https://api.dicebear.com/7.x/bottts/svg?seed=${encodeURIComponent(email)}`;
}

/** Turn `navan.dev@kpriet.ac.in` into `Navan Dev`. */
export function displayNameFor(email: string): string {
  const local = email.split('@')[0] || 'Developer';
  return local
    .split(/[._-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

/** Reads the persisted session. Synchronous, so there is no loading state. */
export function readStoredUser(): AuthUser | null {
  try {
    const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<AuthUser>;
    if (!parsed.email || !parsed.name) return null;
    return {
      name: parsed.name,
      email: parsed.email,
      avatarUrl: parsed.avatarUrl || avatarFor(parsed.email),
    };
  } catch {
    return null;
  }
}
