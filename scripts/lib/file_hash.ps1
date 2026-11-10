function Get-Sha256([string]$Path) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        $file = [IO.File]::OpenRead($Path)
        try { return [BitConverter]::ToString($algorithm.ComputeHash($file)).Replace('-','').ToLowerInvariant() }
        finally { $file.Dispose() }
    } finally { $algorithm.Dispose() }
}
