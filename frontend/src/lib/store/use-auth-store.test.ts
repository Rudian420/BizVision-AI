/**
 * Auth store unit tests — verifies the in-memory state transitions
 * plus the localStorage round-trip on each transition.
 *
 * jsdom (default vitest env) gives us a working `window.localStorage`
 * so we don't need to mock it. Each test resets the store + storage
 * via the `beforeEach` hook so tests don't leak state through the
 * shared singleton.
 */

import { beforeEach, describe, expect, it } from 'vitest';

import type { TokenPair, UserProfile } from '@/lib/auth/types';

import { useAuthStore } from './use-auth-store';

const TOKENS: TokenPair = {
  access_token: 'access-1',
  refresh_token: 'refresh-1',
  token_type: 'bearer',
  expires_in: 1800,
};

const USER: UserProfile = {
  id: '00000000-0000-0000-0000-000000000001',
  email: 'a@b.test',
  full_name: 'Test User',
  company_name: 'Acme',
  role: 'analyst',
  is_active: true,
  is_verified: false,
  created_at: '2026-05-29T00:00:00Z',
};

function resetStore(): void {
  // Direct reset to the initial state — `clear` would also wipe
  // localStorage; both happen here for clean isolation.
  useAuthStore.setState({
    accessToken: null,
    refreshToken: null,
    user: null,
    hydrated: false,
    isAuthenticated: false,
  });
  window.localStorage.clear();
}

describe('useAuthStore', () => {
  beforeEach(resetStore);

  it('starts unauthenticated and unhydrated', () => {
    const s = useAuthStore.getState();
    expect(s.isAuthenticated).toBe(false);
    expect(s.hydrated).toBe(false);
    expect(s.accessToken).toBeNull();
    expect(s.user).toBeNull();
  });

  it('hydrates from localStorage when present', () => {
    window.localStorage.setItem(
      'bizvision.auth',
      JSON.stringify({ accessToken: 'a', refreshToken: 'r', user: USER }),
    );
    useAuthStore.getState().hydrate();
    const s = useAuthStore.getState();
    expect(s.accessToken).toBe('a');
    expect(s.refreshToken).toBe('r');
    expect(s.user?.email).toBe('a@b.test');
    expect(s.isAuthenticated).toBe(true);
    expect(s.hydrated).toBe(true);
  });

  it('hydrate is idempotent and tolerates missing storage', () => {
    useAuthStore.getState().hydrate();
    expect(useAuthStore.getState().hydrated).toBe(true);
    // Second call is a no-op (no exception, no state churn)
    useAuthStore.getState().hydrate();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('hydrate ignores malformed localStorage entries', () => {
    window.localStorage.setItem('bizvision.auth', '{not-json');
    useAuthStore.getState().hydrate();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().hydrated).toBe(true);
  });

  it('setSession writes to state AND localStorage', () => {
    useAuthStore.getState().setSession(TOKENS, USER);
    const s = useAuthStore.getState();
    expect(s.accessToken).toBe('access-1');
    expect(s.refreshToken).toBe('refresh-1');
    expect(s.user?.id).toBe(USER.id);
    expect(s.isAuthenticated).toBe(true);

    const stored = JSON.parse(window.localStorage.getItem('bizvision.auth') ?? '{}');
    expect(stored.accessToken).toBe('access-1');
    expect(stored.user.email).toBe('a@b.test');
  });

  it('setAccessToken updates only the access token but mirrors to storage', () => {
    useAuthStore.getState().setSession(TOKENS, USER);
    useAuthStore.getState().setAccessToken('access-2');
    const s = useAuthStore.getState();
    expect(s.accessToken).toBe('access-2');
    expect(s.refreshToken).toBe('refresh-1');
    expect(s.user?.id).toBe(USER.id);

    const stored = JSON.parse(window.localStorage.getItem('bizvision.auth') ?? '{}');
    expect(stored.accessToken).toBe('access-2');
  });

  it('setUser updates the cached user only when a session exists', () => {
    // No session yet → still updates in-memory user but not storage
    useAuthStore.getState().setUser(USER);
    expect(useAuthStore.getState().user?.email).toBe('a@b.test');
    expect(window.localStorage.getItem('bizvision.auth')).toBeNull();
  });

  it('setUser writes to storage when a session is active', () => {
    useAuthStore.getState().setSession(TOKENS, USER);
    const updated: UserProfile = { ...USER, full_name: 'Renamed User' };
    useAuthStore.getState().setUser(updated);
    const stored = JSON.parse(window.localStorage.getItem('bizvision.auth') ?? '{}');
    expect(stored.user.full_name).toBe('Renamed User');
  });

  it('clear wipes state and storage', () => {
    useAuthStore.getState().setSession(TOKENS, USER);
    useAuthStore.getState().clear();
    const s = useAuthStore.getState();
    expect(s.accessToken).toBeNull();
    expect(s.refreshToken).toBeNull();
    expect(s.user).toBeNull();
    expect(s.isAuthenticated).toBe(false);
    expect(window.localStorage.getItem('bizvision.auth')).toBeNull();
  });
});
