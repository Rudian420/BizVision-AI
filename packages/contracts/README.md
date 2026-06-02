# @bizvision/contracts

The **single source of truth** for the API contract shared between the FastAPI
backend (Python/Pydantic) and the Next.js frontend (TypeScript).

## How it works

```
backend Pydantic schemas  ──▶  /api/v1/openapi.json  ──▶  src/generated/api.ts
        (source of truth)        (OpenAPI 3.1)              (generated TS types)
```

- **Hand-written** (`src/enums.ts`, `src/constants.ts`): cross-language enums and
  values that must stay in lock-step with the backend (risk levels, module names,
  rendering tiers). These mirror the Python enums in
  `backend/src/api/v1/schemas/common.py`.
- **Generated** (`src/generated/api.ts`): full request/response types derived from
  the live backend OpenAPI document via `openapi-typescript`.

## Regenerating types

```bash
# Backend must be running on :8000
npm run contracts:generate            # from the monorepo root
# or, directly against a live server:
npm run generate:from-url --workspace @bizvision/contracts
```

The frontend imports these via the `@bizvision/contracts` path alias.
