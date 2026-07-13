<#
.SYNOPSIS
    Registers a Windows Scheduled Task that runs the Scheduled Prompt
    Runner's MONTHLY prompts at 6:00 AM on the 1st of every month.

.NOTES
    Run this from an elevated (Administrator) PowerShell prompt.

    IMPORTANT: This script uses schtasks.exe exclusively, not the
    PowerShell ScheduledTasks module's Register-ScheduledTask. That's
    deliberate, not an oversight.

    New-ScheduledTaskTrigger has no monthly parameter set at all (only
    Once, Daily, Weekly, AtLogOn, AtStartup). Attempting to work around
    this by building or reusing a CIM MSFT_TaskMonthlyTrigger object and
    passing it through Register-ScheduledTask hits a documented,
    unresolved PowerShell bug (github.com/PowerShell/PowerShell/issues/24651)
    where the CIM class has incorrect property types, causing registration
    to fail with a misleading "user name or password is incorrect" error
    that has nothing to do with the actual credentials supplied.

    schtasks.exe supports monthly triggers natively and correctly, so
    this script uses it exclusively. The tradeoff: schtasks.exe doesn't
    expose the extra settings (WakeToRun, restart-on-failure) that the
    daily/weekly scripts set via New-ScheduledTaskSettingsSet. Acceptable
    here since the target machine never sleeps and is always on AC power.

    This task's action points at run_monthly_tasks.bat, which chains
    both monthly prompts (deprecation, governance) in sequence.
#>

$TaskName = "ScheduledPromptRunner_Monthly"
$ProjectDir = "C:\Projects\scheduled-prompt-runner"
$WrapperBatch = Join-Path $ProjectDir "run_monthly_tasks.bat"

if (-not (Test-Path $WrapperBatch)) {
    Write-Error "Could not find $WrapperBatch. Update `$ProjectDir` in this script, or check your folder structure."
    exit 1
}

$Credential = Get-Credential -Message "Enter your Windows account password (needed so the task can run when you're logged off or the laptop is locked)"
$PlainPassword = $Credential.GetNetworkCredential().Password

$TaskRun = "`"$WrapperBatch`""

$schtasksArgs = @(
    "/create",
    "/tn", $TaskName,
    "/tr", $TaskRun,
    "/sc", "monthly",
    "/d", "1",
    "/st", "06:00",
    "/ru", $Credential.UserName,
    "/rp", $PlainPassword,
    "/rl", "limited",
    "/f"
)

$result = schtasks @schtasksArgs 2>&1
$schtasksExitCode = $LASTEXITCODE

if ($schtasksExitCode -ne 0) {
    Write-Host ""
    Write-Host "Task registration FAILED via schtasks: $result" -ForegroundColor Red
    Write-Host "No task was created. Fix the error above and re-run this script." -ForegroundColor Red
    exit 1
}

try {
    $Verify = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    Write-Host ""
    Write-Host "Task '$TaskName' confirmed registered via schtasks. It will run at 6:00 AM on the 1st of every month." -ForegroundColor Green
    Write-Host "Note: this task does not have the WakeToRun/restart-on-failure settings the daily and weekly tasks have - see script header for why." -ForegroundColor Yellow
    Write-Host "Open Task Scheduler (taskschd.msc) to verify it under the root Task Scheduler Library."
    Write-Host "To test it immediately, run: Start-ScheduledTask -TaskName '$TaskName'"
}
catch {
    Write-Host ""
    Write-Host "schtasks reported success, but Get-ScheduledTask could not find the task: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Check Task Scheduler manually." -ForegroundColor Red
}