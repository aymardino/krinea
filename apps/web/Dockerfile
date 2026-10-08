# Tamis web (Next.js standalone build)
FROM node:22-alpine AS deps
RUN corepack enable
WORKDIR /app
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

FROM node:22-alpine AS build
RUN corepack enable
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY apps/web ./
ARG NEXT_PUBLIC_API_URL=https://api.tamis.app
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

FROM node:22-alpine AS run
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0
WORKDIR /app
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["sh", "-c", "PORT=${PORT:-3000} node server.js"]
