/**
 * Wires the auth store into the api-client's request/response
 * interceptors. Imported by `components/layout/Providers.tsx` so it
 * runs once at client mount, before any API call fires.
 *
 * Kept here (rather than inside the store) to dodge the circular
 * import: `api-client.ts` cannot import the store directly because
 * the store imports types that the client's request shapes depend
 * on. The bridge is one-direction: store → client.
 */

import { configureAuthBridge } from '@/lib/api-client';
import { useAuthStore } from '@/lib/store/use-auth-store';

let installed = false;

export function installAuthBridge(): void {
  if (installed) return;
  configureAuthBridge({
    getAccessToken: () => useAuthStore.getState().accessToken,
    getRefreshToken: () => useAuthStore.getState().refreshToken,
    onTokenRefreshed: (accessToken) => {
      useAuthStore.getState().setAccessToken(accessToken);
    },
    onAuthFailure: () => {
      useAuthStore.getState().clear();
    },
  });
  installed = true;
}
