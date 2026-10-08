# Deploying Aurelius

Three ways to run the same 12 containers:

| Where | Tool | Use it for |
|---|---|---|
| Your laptop | Docker Compose (`deploy/compose`) | Running everything with one command, instead of `start-all.ps1` |
| Your laptop | Helm on Docker Desktop's Kubernetes (`deploy/helm`) | Learning and testing Kubernetes |
| Dev and production clusters | GitHub Actions (`.github/workflows`) | CI builds and pushes images to Artifactory; CD deploys them |

## Where things are

```
agents/*/*/Dockerfile           one per service, next to its code (+ .dockerignore)
mcp-servers/advisor-tools/Dockerfile
frontend/web/Dockerfile         React build served by nginx (nginx/default.conf.template)
deploy/
  compose/docker-compose.yml    all services on one machine
  smoke-test.sh                 end-to-end check, used by CI and CD
  helm/
    aurelius-agent/             ONE generic chart for every service
    values/<service>.yaml       what differs per service: port, env, secrets, size
    environments/<env>.yaml     what differs per environment: registry, host name
    secrets.example.yaml        how to create the Secret (never commit real values)
    deploy-local.ps1            deploy everything to Docker Desktop's Kubernetes
.github/
  services.json                 the list of services (folder, language, port): used by CI and CD
  workflows/ci.yml              build, test, scan, push to Artifactory, integration test
  workflows/cd.yml              deploy to dev, approval, promote, deploy to prod
```

## 1. Docker Compose (start here)

Needs Docker Desktop. Uses your normal `aurelius\.env`.

```powershell
cd C:\work\1_Projects\aurelius\deploy\compose
docker compose up --build -d      # first build takes several minutes
docker compose ps                 # wait until the services show "healthy"
```
Open http://localhost:8080 and sign in with your `DEV_LOGIN_PASSWORD`.

| Command | Does |
|---|---|
| `docker compose logs -f conductor` | Follow one service's logs |
| `docker compose up --build -d conductor` | Rebuild and restart one service after a code change |
| `docker compose down` | Stop everything |

Stop `start-all.ps1` services first: the ports 8000 and 8080 must be free.

## 2. Kubernetes on your laptop

1. Docker Desktop → Settings → Kubernetes → Enable Kubernetes.
2. Run `winget install Helm.Helm`.
3. Build the images with `docker compose build` in `deploy\compose`.
4. Create the namespace and Secret. The commands are at the top of `deploy-local.ps1`.
5. From the `aurelius` folder, run `.\deploy\helm\deploy-local.ps1`.
6. Run `kubectl -n aurelius port-forward svc/web 8080:8080`, then open http://localhost:8080.

Useful commands:

```powershell
kubectl -n aurelius get pods                       # all running?
kubectl -n aurelius logs deploy/conductor          # logs
kubectl -n aurelius describe pod -l app.kubernetes.io/name=librarian   # why isn't it starting?
helm list -n aurelius                              # what's installed, which revision
```

## 3. CI/CD with GitHub Actions and Artifactory

### One-time setup

**In Artifactory, create these repositories:**

| Repository | Type | Holds |
|---|---|---|
| `aurelius-docker-dev` | Docker (local) | Every image CI builds on main, tagged with the commit SHA |
| `aurelius-docker-prod` | Docker (local) | Only the images that passed dev and were approved (CD copies them here) |
| `aurelius-generic-dev` | Generic (local) | The Android app (`.apk`) |

**In GitHub (Settings → Secrets and variables → Actions):**

| Name | Kind | Value |
|---|---|---|
| `ARTIFACTORY_HOST` | Variable | e.g. `mycompany.jfrog.io` |
| `ARTIFACTORY_USER` | Secret | A user that can push and promote |
| `ARTIFACTORY_TOKEN` | Secret | That user's access token |
| `KUBECONFIG_DEV` | Secret | base64 of the dev cluster's kubeconfig |
| `KUBECONFIG_PROD` | Secret | base64 of the prod cluster's kubeconfig |

**GitHub environments (Settings → Environments):**
- Create `dev` and `production`.
- On `production`, add **Required reviewers**. That is the approval gate.

**In each cluster, once:**
- create the namespace (`aurelius-dev` or `aurelius-prod`);
- create the `aurelius-secrets` and `artifactory-pull` Secrets (see `helm/secrets.example.yaml`).

**Also replace `mycompany.jfrog.io` and the host names** in `deploy/helm/environments/dev.yaml` and `prod.yaml`.

### What CI does (`ci.yml`)

| # | Step | Pull request | main |
|---|---|---|---|
| 1 | Detect changed services | Only changed ones | All of them |
| 2 | Set up the toolchain with caches | ✓ | ✓ |
| 3 | Install, lint, unit tests | ✓ | ✓ |
| 4 | Evals gate (Conductor): fail if AI quality drops | ✓ | ✓ |
| 5 | Build the Docker image | ✓ | ✓ |
| 6 | Trivy scan: fail on critical vulnerabilities | ✓ | ✓ |
| 7 | Smoke test: the container starts and `/health` answers | ✓ | ✓ |
| 8 | Push to `aurelius-docker-dev/<service>:<sha>` | | ✓ |
| 9 | Flutter: analyze, test, build APK, upload | If changed | ✓ |
| 10 | Integration: all 12 containers plus `smoke-test.sh` | ✓ | ✓ (pulls the pushed images) |

### What CD does (`cd.yml`)

It runs after CI succeeds on main, or by hand (Actions → CD → Run workflow).

| # | Step |
|---|---|
| 1 | Choose the commit SHA and environment |
| 2 | Verify every image exists in Artifactory |
| 3 | Deploy to dev with Helm, one service at a time (`--atomic`: a failed service rolls itself back) |
| 4 | Smoke test dev: sign in, all agents up, ask a question |
| 5 | **Wait for approval** (the `production` environment) |
| 6 | **Promote** the images from `aurelius-docker-dev` to `aurelius-docker-prod`. This is a copy: same bytes, same tag, nothing rebuilt. |
| 7 | Deploy to production from the prod repo |
| 8 | Smoke test production. If it fails, every service goes back to the revision that was running before. |
| 9 | Tag the release in git (`release-<date>-<sha>`) |

**Rolling back on purpose:** run CD by hand with an older SHA and choose `production`. Images are never deleted, and they're tagged by SHA, so any earlier version can be redeployed.

## Design choices to talk about in an interview

- **Build once, deploy many.** The image tested in CI is the exact image that runs in production. CD promotes it and never rebuilds it.
- **Immutable tags.** Images are tagged with the git SHA, never `latest`, so you always know which code is running.
- **One chart for 12 services.** The uniform agent contract (one port, `/health`, `/invoke`) made deployment uniform too.
- **Least privilege:**
  - Each service gets only the secrets it needs (the Liaison never sees the Anthropic key).
  - Containers run as non-root with all Linux capabilities dropped.
  - Only the web app is reachable from outside; the agents are internal only.
- **Small, safe images:**
  - Multi-stage builds, so there are no compilers in the runtime images.
  - Pulse is a distroless image of about 10 MB.
  - The Librarian's embedding model is baked in at build time.
- **Health probes.** Startup, readiness and liveness all use `/health`. A rolling update only moves traffic to a new pod once it reports ready.
- **AI quality gate.** The evals run in CI like unit tests, so a prompt or model change that makes routing or guardrails worse can't be merged.

### Known limits (and what you'd do next)

- **The Conductor runs as one copy.** Its conversation memory, rate limits and daily cost cap live in memory. To scale it out, move them to Redis.
- **The Librarian's index is rebuilt in every pod at startup.** At scale, use a shared vector database (pgvector, OpenSearch) filled by a separate ingestion job.
- **Action versions.** For a bank, pin GitHub Actions to commit SHAs, not version tags, and add image signing (cosign) and an SBOM.
