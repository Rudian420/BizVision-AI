/**
 * `useAuthStore` — central client-side state for authentication.
 *
 * Owns:
 *   • the access + refresh tokens (kept in memory; mirrored to
 *     localStorage so a page reload doesn't log the user out)
 *   • the cached user profile
 *   • lifecycle flags (`hydrated`, `isAuthenticated`)
 *
 * The api-client (`lib/api-client.ts`) does NOT import this store
 * directly — it calls `configureAuthBridge` at module-load time
 * (wired in `components/layout/Providers.tsx`) so the request /
 * response interceptors can read tokens and react to refresh events
 * without a circular import.
 */

import { create } from 'zustand';

import type { TokenPair, UserProfile } from '@/lib/auth/types';

/** Storage key for the refresh token. Access token lives in memory only —
 *  short-lived (30 min) so the security benefit of localStorage avoidance
 *  is tiny, and the UX hit of re-logging on tab close would be real. */
const TOKEN_STORAGE_KEY = 'bizvision.auth';

type PersistedAuth = {
  accessToken: string;
  refreshToken: string;
  user: UserProfile | null;
};

function readPersisted(): PersistedAuth | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(TOKEN_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as PersistedAuth;
  } catch {
    return null;
  }
}

function writePersisted(value: PersistedAuth | null): void {
  if (typeof window === 'undefined') return;
  try {
    if (value === null) {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    } else {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify(value));
    }
  } catch {
    // localStorage may be unavailable (private-mode Safari, etc.) —
    // we lose persistence but in-memory state still works.
  }
}

type AuthState = {
  accessToken: string | null;
  refreshToken: string | null;
  user: UserProfile | null;
  hydrated: boolean;

  // ── derived (cheap selectors) ─────────────────────────────────
  isAuthenticated: boolean;

  // ── actions ───────────────────────────────────────────────────
  /** Called on first client mount to read persisted tokens. */
  hydrate: () => void;
  /** Set tokens + user after a successful login or register. */
  setSession: (tokens: TokenPair, user: UserProfile) => void;
  /** Update only the access token (refresh response, no user change). */
  setAccessToken: (accessToken: string) => void;
  /** Cache an updated user profile (e.g. after /auth/me). */
  setUser: (user: UserProfile) => void;
  /** Wipe everything. Called on logout AND on terminal 401. */
  clear: () => void;
};

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: null,
  refreshToken: null,
  user: null,
  hydrated: false,
  isAuthenticated: false,

  hydrate: () => {
    if (get().hydrated) return;
    const stored = readPersisted();
    if (stored) {
      set({
        accessToken: stored.accessToken,
        refreshToken: stored.refreshToken,
        user: stored.user,
        isAuthenticated: !!stored.accessToken,
        hydrated: true,
      });
    } else {
      set({ hydrated: true });
    }
  },

  setSession: (tokens, user) => {
    writePersisted({
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
      user,
    });
    set({
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
      user,
      isAuthenticated: true,
    });
  },

  setAccessToken: (accessToken) => {
    const { refreshToken, user } = get();
    if (refreshToken) {
      writePersisted({ accessToken, refreshToken, user });
    }
    set({ accessToken, isAuthenticated: true });
  },

  setUser: (user) => {
    const { accessToken, refreshToken } = get();
    if (accessToken && refreshToken) {
      writePersisted({ accessToken, refreshToken, user });
    }
    set({ user });
  },

  clear: () => {
    writePersisted(null);
    set({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
    });
  },
}));

/** Selectors (stable references for `useAuthStore(s => s.user)` reads). */
export const selectIsAuthenticated = (s: AuthState): boolean => s.isAuthenticated;
export const selectUser = (s: AuthState): UserProfile | null => s.user;
export const selectHydrated = (s: AuthState): boolean => s.hydrated;
