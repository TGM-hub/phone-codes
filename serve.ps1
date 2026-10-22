# Local preview without Python: a tiny static server on http://localhost:8000/
# (the app loads data/*.json with fetch, which does not work from file://)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$port = 8000
$types = @{ ".html"="text/html; charset=utf-8"; ".json"="application/json; charset=utf-8"; ".js"="text/javascript";
            ".css"="text/css"; ".png"="image/png"; ".svg"="image/svg+xml"; ".ico"="image/x-icon" }
$l = New-Object System.Net.HttpListener
$l.Prefixes.Add("http://localhost:$port/")
try { $l.Start() } catch { Write-Host "Port $port deja pris : ferme l'autre fenetre serve, ou change `$port." -ForegroundColor Yellow; Read-Host "Entree pour fermer"; exit 1 }
Write-Host "Serveur sur http://localhost:$port/  (ferme cette fenetre pour l'arreter)" -ForegroundColor Green
Start-Process "http://localhost:$port/"
while ($l.IsListening) {
    $ctx = $l.GetContext()
    $rel = [Uri]::UnescapeDataString($ctx.Request.Url.AbsolutePath.TrimStart("/"))
    if (-not $rel) { $rel = "index.html" }
    $path = [IO.Path]::GetFullPath((Join-Path $root $rel))
    $res = $ctx.Response
    if ($path.StartsWith($root) -and (Test-Path -LiteralPath $path -PathType Leaf)) {
        $bytes = [IO.File]::ReadAllBytes($path)
        $ext = [IO.Path]::GetExtension($path).ToLower()
        $res.ContentType = if ($types[$ext]) { $types[$ext] } else { "application/octet-stream" }
        $res.Headers.Add("Cache-Control", "no-store")
        $res.OutputStream.Write($bytes, 0, $bytes.Length)
    } else { $res.StatusCode = 404 }
    $res.Close()
}
