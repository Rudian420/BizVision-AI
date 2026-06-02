#!/usr/bin/env node
/**
 * Generate TypeScript types from the backend OpenAPI document.
 *
 * Strategy:
 *   1. If the backend is running, pull the live spec from
 *      http://localhost:8000/api/v1/openapi.json.
 *   2. Otherwise, fall back to a committed snapshot at ./openapi.snapshot.json
 *      if present; else leave the placeholder and warn.
 */
import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const out = resolve(__dirname, '../src/generated/api.ts');
const snapshot = resolve(__dirname, '../openapi.snapshot.json');
const url = process.env.OPENAPI_URL ?? 'http://localhost:8000/api/v1/openapi.json';

function run(input) {
  execFileSync('npx', ['openapi-typescript', input, '-o', out], {
    stdio: 'inherit',
    shell: process.platform === 'win32',
  });
}

try {
  const res = await fetch(url, { signal: AbortSignal.timeout(2500) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  console.log(`[contracts] Generating from live backend: ${url}`);
  run(url);
  console.log(`[contracts] Wrote ${out}`);
} catch {
  if (existsSync(snapshot)) {
    console.warn(`[contracts] Backend unreachable — using snapshot ${snapshot}`);
    run(snapshot);
  } else {
    console.warn(
      '[contracts] Backend unreachable and no snapshot found. ' +
        'Start the backend (make backend-dev) then re-run. Placeholder kept.',
    );
    process.exit(0);
  }
}
