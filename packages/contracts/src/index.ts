/**
 * @bizvision/contracts — shared API contract surface.
 *
 * Re-exports hand-written enums/constants plus the generated OpenAPI types
 * (available after running `npm run contracts:generate`).
 */

export * from './enums';
export * from './constants';

// Generated OpenAPI types. Present after `npm run contracts:generate`.
// A committed placeholder keeps type-checking green before first generation.
export type { paths, components, operations } from './generated/api';
