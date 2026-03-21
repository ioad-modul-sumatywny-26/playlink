FROM oven/bun:1-slim AS base
WORKDIR /usr/src/app

FROM base AS build
# Copy configuration and dependency files
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

# Copy source and env files
COPY . .
# SvelteKit static env variables must be available at build time.
# We use .env.example as a fallback if .env is missing.
RUN cp .env.example .env || true
RUN bun run build

FROM base AS runtime
# Only copy production dependencies and the built application
COPY --from=build /usr/src/app/package.json /usr/src/app/bun.lock ./
RUN bun install --production --frozen-lockfile

COPY --from=build /usr/src/app/build ./build
COPY --from=build /usr/src/app/static ./static

ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=3000
EXPOSE 3000

# The adapter-node output is in build/index.js
CMD ["bun", "run", "build/index.js"]
