# Notary (onboarding-kyc) container image. Two stages:
#   build   : Maven + full JDK compile the code into one runnable jar
#   runtime : only a Java runtime (JRE) and that jar. Much smaller, nothing to compile with.
#
# Build (from this folder):   docker build -t aurelius/notary:local .
# Run:                        docker run --rm -p 8201:8201 --env-file ..\..\..\.env aurelius/notary:local
#
# Tests are skipped here on purpose: CI runs "mvn verify" BEFORE building the image.

# ---------- stage 1: build ----------
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build
# Download dependencies first, so they're cached until pom.xml changes
COPY pom.xml .
RUN --mount=type=cache,target=/root/.m2 mvn -B -q dependency:go-offline
COPY src ./src
RUN --mount=type=cache,target=/root/.m2 mvn -B -q -DskipTests package

# ---------- stage 2: runtime ----------
FROM eclipse-temurin:21-jre
ENV NOTARY_HOST=0.0.0.0
WORKDIR /app
COPY --from=build /build/target/notary.jar app.jar
COPY data ./data
RUN useradd --uid 10001 --create-home app && mkdir -p logs && chown -R 10001:10001 /app
USER 10001

EXPOSE 8201
# No HEALTHCHECK here (the slim JRE image has no curl). Kubernetes probes and
# docker compose check /health from outside instead.

# MaxRAMPercentage: let Java size its memory from the container limit, not the host's RAM
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75", "-jar", "app.jar"]
