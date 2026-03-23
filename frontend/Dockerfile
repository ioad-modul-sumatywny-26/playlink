FROM oven/bun:1-slim AS base
WORKDIR /usr/src/app

FROM base AS build
# Copy configuration and dependency files
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

# Copy source files. Public runtime env vars are injected by the server process,
# so we don't need to bake a local .env file into the image.
COPY . .
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
