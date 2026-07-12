<#
.SYNOPSIS
    Registers a Windows Scheduled Task that runs the Scheduled Prompt
    Runner's DAILY prompt every day at 5:00 AM.

.NOTES
    Run this from an elevated (Administrator) PowerShell prompt.
#>

$TaskName = "ScheduledPromptRunner_Daily"
$ProjectDir = "C:\Projects\scheduled-prompt-runner"
$BatchFile = Join-Path $ProjectDir "run_prompt.bat"

if (-not (Test-Path $BatchFile)) {
    Write-Error "Could not find $BatchFile. Update `$ProjectDir` in this script, or check your folder structure."
    exit 1
}

$Action = New-ScheduledTaskAction -Execute $BatchFile -Argument "daily" -WorkingDirectory $ProjectDir

$Trigger = New-ScheduledTaskTrigger -Daily -At 5:00AM

$Settings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5)

$Credential = Get-Credential -Message "Enter your Windows account password (needed so the task can run when you're logged off or the laptop is locked)"

try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -User $Credential.UserName `
        -Password $Credential.GetNetworkCredential().Password `
        -RunLevel Limited `
        -Description "Runs the Scheduled Prompt Runner's daily prompt every day at 5:00 AM." `
        -Force `
        -ErrorAction Stop | Out-Null

    $Verify = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop

    Write-Host ""
    Write-Host "Task '$TaskName' confirmed registered. It will run every day at 5:00 AM." -ForegroundColor Green
    Write-Host "Open Task Scheduler (taskschd.msc) to verify it under the root Task Scheduler Library."
    Write-Host "To test it immediately, run: Start-ScheduledTask -TaskName '$TaskName'"
}
catch {
    Write-Host ""
    Write-Host "Task registration FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "No task was created. Fix the error above and re-run this script." -ForegroundColor Red
    exit 1
}