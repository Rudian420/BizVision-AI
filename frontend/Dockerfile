# ============================================================
# BizVision AI - Frontend Dockerfile
# Multi-stage: development (hot reload) + production (optimized)
#
# Build context = monorepo root (docker-compose sets context: .)
# WORKDIR /app = monorepo root inside the container.
# The Next.js dev server runs from /app/frontend so workspace deps
# (@bizvision/contracts) resolve through the root node_modules.
# ============================================================

FROM node:20-alpine AS base

RUN apk add --no-cache libc6-compat curl
WORKDIR /app

# Copy the workspace manifests needed for `npm install` to plan the tree.
# We bring the root package.json + lock, the frontend workspace's own
# package.json, and the entire packages/ tree (small; just JSON +
# generated TS).
COPY package.json package-lock.json* ./
COPY frontend/package.json ./frontend/
COPY packages/ ./packages/

# -------------------------------------------------------------
# DEPENDENCIES stage
# -------------------------------------------------------------
FROM base AS deps
RUN npm install --no-audit --no-fund --legacy-peer-deps

# -------------------------------------------------------------
# DEVELOPMENT stage
# -------------------------------------------------------------
FROM base AS development
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NODE_ENV=development
WORKDIR /app/frontend
CMD ["npm", "run", "dev"]

# -------------------------------------------------------------
# BUILD stage
# -------------------------------------------------------------
FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NODE_ENV=production
WORKDIR /app/frontend
RUN npm run build

# -------------------------------------------------------------
# PRODUCTION stage
# -------------------------------------------------------------
FROM node:20-alpine AS production

WORKDIR /app
ENV NODE_ENV=production

RUN addgroup --gid 1001 --system nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/frontend/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/frontend/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/frontend/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
