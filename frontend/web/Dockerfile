# Atrium web app container image. Two stages:
#   build   : Node type-checks and builds the React app into static files (dist/)
#   runtime : nginx serves those files and forwards /v1/... to the Conductor.
#             No Node.js in the final image.
#
# Build (from this folder):   docker build -t aurelius/web:local .
# Run:                        docker run --rm -p 8080:8080 -e CONDUCTOR_URL=http://host.docker.internal:8000 aurelius/web:local
#                             then open http://localhost:8080

# ---------- stage 1: build ----------
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# ---------- stage 2: runtime ----------
# "unprivileged" = nginx runs as a normal user (uid 101) and listens on 8080, not 80
FROM nginxinc/nginx-unprivileged:1.27-alpine
# Where the Conductor is. Compose: http://conductor:8000 ; Kubernetes: set by the Helm values.
ENV CONDUCTOR_URL=http://conductor:8000 \
    NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1
# Files in /etc/nginx/templates get ${VARIABLES} filled in when the container starts
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
USER 101

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
