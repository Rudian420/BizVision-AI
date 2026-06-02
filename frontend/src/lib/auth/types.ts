/**
 * Hand-written auth contract types.
 *
 * These mirror the backend Pydantic schemas in
 * `backend/src/api/v1/schemas/auth.py`. We keep them local rather
 * than importing from `@bizvision/contracts` because the generated
 * OpenAPI surface is still a placeholder; once the contracts
 * generator runs against the live backend these can be replaced
 * with `components['schemas']['…']` references.
 */

/** Backend `UserRole` enum. */
export type UserRole = 'admin' | 'analyst' | 'viewer';

export type UserProfile = {
  id: string;
  email: string;
  full_name?: string | null;
  company_name?: string | null;
  role: UserRole;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
};

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number;
};

export type UserLoginResponse = {
  tokens: TokenPair;
  user: UserProfile;
};

export type UserRegisterRequest = {
  email: string;
  password: string;
  full_name?: string;
  company_name?: string;
};

export type UserLoginRequest = {
  email: string;
  password: string;
};

export type TokenRefreshResponse = {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
};
