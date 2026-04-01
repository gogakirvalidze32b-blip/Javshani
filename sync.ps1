$keyPath = "C:\Users\For Home\Downloads\ssh-key-2026-03-28.key"
$remoteFile = "ubuntu@130.61.41.121:/home/ubuntu/users.json"
$localFile = "C:\Users\For Home\Desktop\Javshani-main\users.json"

Write-Host "--- Syncing users.json from Server ---" -ForegroundColor Cyan

while($true) {
    try {
        scp -i $keyPath $remoteFile $localFile
        $time = Get-Date -Format "HH:mm:ss"
        Write-Host "[$time] SUCCESS: Users database updated." -ForegroundColor Green
    } catch {
        Write-Host "[$time] ERROR: Connection failed!" -ForegroundColor Red
    }
    Start-Sleep -Seconds 300
}