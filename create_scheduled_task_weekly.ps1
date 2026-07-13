<#
.SYNOPSIS
    Registers a Windows Scheduled Task that runs the Scheduled Prompt
    Runner's WEEKLY prompt every Sunday at 5:30 AM.

.NOTES
    Run this from an elevated (Administrator) PowerShell prompt.
#>

$TaskName = "ScheduledPromptRunner_Weekly"
$ProjectDir = "C:\Projects\scheduled-prompt-runner"
$WrapperBatch = Join-Path $ProjectDir "run_weekly_tasks.bat"

if (-not (Test-Path $WrapperBatch)) {
    Write-Error "Could not find $WrapperBatch. Update `$ProjectDir` in this script, or check your folder structure."
    exit 1
}

$Action = New-ScheduledTaskAction -Execute $WrapperBatch -WorkingDirectory $ProjectDir

$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 5:30AM

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
        -Description "Runs the Scheduled Prompt Runner's weekly prompt every Sunday at 5:30 AM." `
        -Force `
        -ErrorAction Stop | Out-Null

    $Verify = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop

    Write-Host ""
    Write-Host "Task '$TaskName' confirmed registered. It will run every Sunday at 5:30 AM." -ForegroundColor Green
    Write-Host "Open Task Scheduler (taskschd.msc) to verify it under the root Task Scheduler Library."
    Write-Host "To test it immediately, run: Start-ScheduledTask -TaskName '$TaskName'"
}
catch {
    Write-Host ""
    Write-Host "Task registration FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "No task was created. Fix the error above and re-run this script." -ForegroundColor Red
    exit 1
}