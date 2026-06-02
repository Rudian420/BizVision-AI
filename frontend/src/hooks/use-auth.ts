/**
 * `useAuth` — convenience hook for components that need to read the
 * auth state and trigger the common actions (login / register /
 * logout). Avoids re-implementing the same `useAuthStore`
 * selectors in every form / page.
 */

'use client';

import { useCallback } from 'react';

import { loginUser, logoutUser, registerUser } from '@/lib/auth/client';
import type { UserLoginRequest, UserRegisterRequest } from '@/lib/auth/types';
import { useAuthStore } from '@/lib/store/use-auth-store';

export function useAuth() {
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const hydrated = useAuthStore((s) => s.hydrated);
  const setSession = useAuthStore((s) => s.setSession);
  const clear = useAuthStore((s) => s.clear);

  const login = useCallback(
    async (body: UserLoginRequest) => {
      const response = await loginUser(body);
      setSession(response.tokens, response.user);
      return response;
    },
    [setSession],
  );

  const register = useCallback(
    async (body: UserRegisterRequest) => {
      const response = await registerUser(body);
      setSession(response.tokens, response.user);
      return response;
    },
    [setSession],
  );

  const logout = useCallback(async () => {
    const refresh = useAuthStore.getState().refreshToken;
    if (refresh) {
      try {
        await logoutUser(refresh);
      } catch {
        // Best-effort — the server may already have invalidated the
        // refresh token; either way we wipe local state below.
      }
    }
    clear();
  }, [clear]);

  return { user, isAuthenticated, hydrated, login, register, logout };
}
