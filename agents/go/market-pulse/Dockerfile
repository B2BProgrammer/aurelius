# Pulse (market-pulse) container image. Two stages:
#   build   : the Go toolchain compiles ONE static binary
#   runtime : "distroless" = just that binary + its data. No shell, no package manager,
#             so there is almost nothing for an attacker to use. About 10 MB in total.
#
# Build (from this folder):   docker build -t aurelius/pulse:local .
# Run:                        docker run --rm -p 8301:8301 --env-file ..\..\..\.env aurelius/pulse:local

# ---------- stage 1: build ----------
FROM golang:1.24 AS build
WORKDIR /src
COPY go.mod ./
COPY cmd ./cmd
COPY internal ./internal
# CGO_ENABLED=0: a fully static binary that runs without any C libraries
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/pulse ./cmd/pulse

# ---------- stage 2: runtime ----------
FROM gcr.io/distroless/static-debian12:nonroot
ENV PULSE_HOST=0.0.0.0
WORKDIR /app
COPY --from=build /out/pulse /app/pulse
COPY data /app/data
# 65532 = the "nonroot" user built into distroless images
USER 65532:65532

EXPOSE 8301
# No HEALTHCHECK: distroless has no shell or curl. Kubernetes probes and
# docker compose check /health from outside instead.
ENTRYPOINT ["/app/pulse"]
