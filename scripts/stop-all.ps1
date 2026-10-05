# Stops every Aurelius service by finding whatever is listening on its port.
$ports = 8500, 8004, 8102, 8001, 8002, 8003, 8101, 8201, 8202, 8301, 8000, 5173

foreach ($port in $ports) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { Write-Host "Port $port : not running"; continue }
    foreach ($c in $conns) {
        Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
        Write-Host "Port $port : stopped (process $($c.OwningProcess))" -ForegroundColor Yellow
    }
}
Write-Host "Done. You can close the leftover PowerShell windows." -ForegroundColor Cyan