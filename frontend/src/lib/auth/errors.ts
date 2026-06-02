/**
 * Friendly error formatting for backend auth failures.
 *
 * The FastAPI backend surfaces validation/auth failures as
 * `{ detail: string | ValidationError[] }`. Pydantic
 * `ValidationError` becomes an array of `{ loc, msg, type }` — we
 * surface only `msg` to keep the form copy readable.
 */

import axios from 'axios';

type PydanticErrorItem = {
  loc?: unknown[];
  msg?: string;
  type?: string;
};

function extractDetail(detail: unknown): string | null {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (item && typeof item === 'object') {
          const msg = (item as PydanticErrorItem).msg;
          if (typeof msg === 'string' && msg.length > 0) return msg;
        }
        return null;
      })
      .filter((m): m is string => m !== null);
    if (messages.length > 0) return messages.join('; ');
  }
  return null;
}

export function formatAuthError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { detail?: unknown } | undefined;
    if (data) {
      const msg = extractDetail(data.detail);
      if (msg) return msg;
    }
    if (error.response?.status === 401) return 'Invalid email or password.';
    if (error.response?.status === 409) return 'That account already exists.';
    if (error.code === 'ERR_NETWORK') {
      return "Couldn't reach the backend — check it's running.";
    }
    if (error.message) return error.message;
  }
  if (error instanceof Error && error.message) return error.message;
  return 'Something went wrong. Please try again.';
}
