# Liaison (crm-sync) container image. Two stages:
#   build   : installs ALL packages (incl. TypeScript) and compiles src/*.ts -> dist/*.js
#   runtime : only production packages + the compiled JavaScript. No compiler, no tsx.
#
# Build (from this folder):   docker build -t aurelius/liaison:local .
# Run:                        docker run --rm -p 8102:8102 --env-file ..\..\..\.env aurelius/liaison:local

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
    LIAISON_HOST=0.0.0.0
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --from=build /app/dist ./dist
COPY --chown=1000:1000 data ./data
# "node" (uid 1000) is the normal user that comes with the image
RUN mkdir -p logs && chown -R 1000:1000 /app
USER 1000

EXPOSE 8102
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:8102/health').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", "dist/server.js"]
