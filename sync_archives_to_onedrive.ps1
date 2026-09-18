$AzureUser = "azureuser"
$AzureHost = "20.213.77.211"

$Key = "$env:USERPROFILE\.ssh\id_ed25519"

$RemoteRoot = "/home/azureuser/OneDrive/BridgeDigitalTwin/Archive"

$LocalRoot = "$env:USERPROFILE\OneDrive - Monash University\BridgeDigitalTwin\Archive"

Write-Host "============================================"
Write-Host "Bridge Digital Twin Archive Sync"
Write-Host "============================================"

$RemoteFiles = ssh -i $Key "$AzureUser@$AzureHost" `
    "find '$RemoteRoot' -type f -name '*.parquet'"

if (-not $RemoteFiles) {
    Write-Host "No Parquet files waiting on Azure."
    exit 0
}

foreach ($RemoteFile in $RemoteFiles) {

    Write-Host ""
    Write-Host "Processing:"
    Write-Host $RemoteFile

    $RelativePath = $RemoteFile.Replace(
        "$RemoteRoot/",
        ""
    )

    $RelativeDirectory = Split-Path `
        $RelativePath `
        -Parent

    $FileName = Split-Path `
        $RemoteFile `
        -Leaf

    $LocalDirectory = Join-Path `
        $LocalRoot `
        $RelativeDirectory

    New-Item `
        -ItemType Directory `
        -Force `
        -Path $LocalDirectory `
        | Out-Null

    $LocalFile = Join-Path `
        $LocalDirectory `
        $FileName

    $RemoteSize = ssh -i $Key `
        "$AzureUser@$AzureHost" `
        "stat -c %s '$RemoteFile'"

    $RemoteSize = [int64]$RemoteSize

    Write-Host "Azure size: $RemoteSize bytes"
    Write-Host "Copying to Monash OneDrive..."

    scp -i $Key `
        "${AzureUser}@${AzureHost}:$RemoteFile" `
        "$LocalDirectory"

    if (-not (Test-Path $LocalFile)) {
        Write-Host "ERROR: Local file was not created."
        Write-Host "Azure file will NOT be deleted."
        continue
    }

    $LocalSize = (Get-Item $LocalFile).Length

    Write-Host "Local size: $LocalSize bytes"

    if ($LocalSize -eq $RemoteSize) {

        Write-Host "Verification successful."
        Write-Host "Deleting temporary Azure archive..."

        ssh -i $Key `
            "$AzureUser@$AzureHost" `
            "rm '$RemoteFile'"

        Write-Host "Azure temporary file deleted."
    }
    else {
        Write-Host "VERIFICATION FAILED."
        Write-Host "Azure file will NOT be deleted."
    }
}

Write-Host ""
Write-Host "============================================"
Write-Host "Archive sync completed."
Write-Host "TimescaleDB data was NOT deleted."
Write-Host "============================================"