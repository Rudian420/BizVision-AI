/** Typed, validated access to public runtime configuration. */
import { z } from 'zod';

const schema = z.object({
  NEXT_PUBLIC_API_URL: z.string().url().default('http://localhost:8000/api/v1'),
  NEXT_PUBLIC_WS_URL: z.string().default('ws://localhost:8000/ws'),
  NEXT_PUBLIC_APP_NAME: z.string().default('BizVision AI'),
  NEXT_PUBLIC_APP_VERSION: z.string().default('1.0.0'),
  NEXT_PUBLIC_ENABLE_3D: z
    .enum(['true', 'false'])
    .default('true')
    .transform((v) => v === 'true'),
});

export const env = schema.parse({
  NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL,
  NEXT_PUBLIC_APP_NAME: process.env.NEXT_PUBLIC_APP_NAME,
  NEXT_PUBLIC_APP_VERSION: process.env.NEXT_PUBLIC_APP_VERSION,
  NEXT_PUBLIC_ENABLE_3D: process.env.NEXT_PUBLIC_ENABLE_3D,
});
