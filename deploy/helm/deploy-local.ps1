<#
  Deploy all Aurelius services to Docker Desktop's Kubernetes, using locally built images.

  Before the first run:
    1. Docker Desktop -> Settings -> Kubernetes -> Enable Kubernetes
    2. Install Helm:  winget install Helm.Helm
    3. Build the images:  cd deploy\compose ; docker compose build
    4. Create the secret (once):
         kubectl create namespace aurelius
         kubectl -n aurelius create secret generic aurelius-secrets `
           --from-literal=SERVICE_TOKEN=<48 random chars> --from-literal=JWT_SIGNING_KEY=<64 random chars> `
           --from-literal=ANTHROPIC_API_KEY= --from-literal=DEV_LOGIN_PASSWORD=<demo password>

  Run (from the aurelius folder):   .\deploy\helm\deploy-local.ps1
  Remove everything:                .\deploy\helm\deploy-local.ps1 -Uninstall
#>
param([switch]$Uninstall)
$ErrorActionPreference = "Stop"
$ns = "aurelius"
$chart = Join-Path $PSScriptRoot "aurelius-agent"
# MCP server and agents first, Conductor and web last (they depend on the others)
$services = @("advisor-tools", "sentinel", "librarian", "analyst", "scribe", "herald",
              "liaison", "notary", "actuary", "pulse", "conductor", "web")

if ($Uninstall) {
    foreach ($s in $services) { helm uninstall $s -n $ns --ignore-not-found }
    return
}

foreach ($s in $services) {
    Write-Host "== $s" -ForegroundColor Cyan
    helm upgrade --install $s $chart -n $ns `
        -f (Join-Path $PSScriptRoot "values\$s.yaml") `
        -f (Join-Path $PSScriptRoot "environments\local.yaml") `
        --wait --timeout 5m
    if ($LASTEXITCODE -ne 0) { throw "$s failed to deploy. Look with: kubectl -n $ns describe pod -l app.kubernetes.io/name=$s" }
}

kubectl -n $ns get pods
Write-Host "`nAll deployed. Open the web app with:" -ForegroundColor Green
Write-Host "  kubectl -n $ns port-forward svc/web 8080:8080     then http://localhost:8080"
