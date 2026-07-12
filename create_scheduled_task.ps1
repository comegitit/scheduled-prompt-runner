<#
.SYNOPSIS
    Registers a Windows Scheduled Task that runs the Scheduled Prompt Runner
    every Sunday at 5:00 AM, including waking the laptop from sleep if needed.

.NOTES
    Run this from an elevated (Administrator) PowerShell prompt.
    Update $ProjectDir below if your folder location differs.
#>

$TaskName = "ScheduledPromptRunner"
$ProjectDir = "C:\Projects\scheduled-prompt-runner"
$BatchFile = Join-Path $ProjectDir "run_prompt.bat"

if (-not (Test-Path $BatchFile)) {
    Write-Error "Could not find $BatchFile. Update `$ProjectDir` in this script, or check your folder structure."
    exit 1
}

$Action = New-ScheduledTaskAction -Execute $BatchFile -WorkingDirectory $ProjectDir

$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 5:00AM

$Settings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5)

# "Run whether user is logged on or not" requires storing the account
# password with the task. You'll be prompted for it here.
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
        -Description "Runs the Scheduled Prompt Runner every Sunday at 5:00 AM." `
        -Force `
        -ErrorAction Stop | Out-Null

    # Confirm it actually exists before declaring success - don't just
    # trust that Register-ScheduledTask didn't throw.
    $Verify = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop

    Write-Host ""
    Write-Host "Task '$TaskName' confirmed registered. It will run every Sunday at 5:00 AM." -ForegroundColor Green
    Write-Host "Open Task Scheduler (taskschd.msc) to verify it under the root Task Scheduler Library."
    Write-Host "To test it immediately, run: Start-ScheduledTask -TaskName '$TaskName'"
}
catch {
    Write-Host ""
    Write-Host "Task registration FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "No task was created. Fix the error above and re-run this script." -ForegroundColor Red
    exit 1
}