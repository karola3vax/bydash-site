param(
  [int]$Port = 4193
)

Set-Location $PSScriptRoot
$env:HOST = "127.0.0.1"
python server.py $Port
