# Herald (client-comms) container image. Two stages:
#   build   : installs ALL packages (incl. TypeScript) and compiles src/*.ts -> dist/*.js
#   runtime : only production packages + the compiled JavaScript. No compiler, no tsx.
#
# Build (from this folder):   docker build -t aurelius/herald:local .
# Run:                        docker run --rm -p 8101:8101 --env-file ..\..\..\.env aurelius/herald:local

# ---------- stage 1: build ----------
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json tsconfig.build.json ./
COPY src ./src
RUN npm run build

# ---------- stage 2: runtime ----------
FROM node:22-slim
ENV NODE_ENV=production \
    HERALD_HOST=0.0.0.0
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --from=build /app/dist ./dist
# "node" (uid 1000) is the normal user that comes with the image
RUN mkdir -p logs && chown -R 1000:1000 /app
USER 1000

EXPOSE 8101
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:8101/health').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", "dist/server.js"]
