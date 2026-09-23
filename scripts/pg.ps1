<#
.SYNOPSIS
  Start/stop/status for the nokia PostgreSQL cluster on port 5434.

.DESCRIPTION
  This project uses a dedicated PG16 cluster on port 5434 because tentoro
  occupies 5432/5433. It is NOT registered as a Windows service (that needs
  admin), so it does not survive a reboot -- run `pg.ps1 start` after logging in.

.EXAMPLE
  ./scripts/pg.ps1 start
  ./scripts/pg.ps1 status
  ./scripts/pg.ps1 stop
#>
param(
  [Parameter(Position = 0)]
  [ValidateSet('start', 'stop', 'status', 'restart', 'psql', 'log')]
  [string]$Action = 'status'
)

$ErrorActionPreference = 'Stop'

$PgBin   = 'C:\Program Files\PostgreSQL\16\bin'
$DataDir = 'C:\Users\user\pgdata\nokia5434'
$LogFile = Join-Path $DataDir 'server.log'
$Port    = 5434

function Test-Up {
  & "$PgBin\pg_isready.exe" -h 127.0.0.1 -p $Port *> $null
  return ($LASTEXITCODE -eq 0)
}

switch ($Action) {
  'start' {
    if (Test-Up) { Write-Host "already running on port $Port"; break }
    # Start-Process detaches the postmaster from this shell's process tree,
    # so closing the terminal (or a tool killing it) does not take the DB down.
    Start-Process -FilePath "$PgBin\pg_ctl.exe" `
      -ArgumentList '-D', "`"$DataDir`"", '-l', "`"$LogFile`"", 'start' `
      -WindowStyle Hidden
    for ($i = 0; $i -lt 30; $i++) { if (Test-Up) { break }; Start-Sleep -Milliseconds 300 }
    if (Test-Up) { Write-Host "started on port $Port" } else { Write-Error "failed to start; see $LogFile" }
  }
  'stop' {
    & "$PgBin\pg_ctl.exe" -D "$DataDir" -m fast stop
  }
  'restart' {
    & "$PSCommandPath" stop; & "$PSCommandPath" start
  }
  'status' {
    if (Test-Up) { Write-Host "UP   - 127.0.0.1:$Port ($DataDir)" }
    else { Write-Host "DOWN - $DataDir" }
  }
  'psql' {
    & "$PgBin\psql.exe" -h 127.0.0.1 -p $Port -U nokia_app -d nokia
  }
  'log' {
    Get-Content $LogFile -Tail 40
  }
}
