"""The Task Scheduler definition that starts `oeisbot daemon` each night (item 58).

Written by `oeisbot daemon --task-xml FILE` for the user to import:

    oeisbot daemon --task-xml oeisbot-daemon.xml
    schtasks /create /tn "OEISBot daemon" /xml oeisbot-daemon.xml

(Give the file name; do not redirect the printed form. The definition declares UTF-16, and only the
command writes that in every shell.)

Nothing in this project registers, changes or removes a scheduled task: that is the user's to do.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from . import config

TASK_NAME = "OEISBot daemon"


def _quoted(path: Path) -> str:
    """A program path as Task Scheduler wants it: in quotes when it has a space, or the part after the
    space is taken for an argument."""
    text = str(path)
    return f'"{text}"' if " " in text else text


def write_task(target: Path, window, **kwargs) -> Path:
    """Write the definition to `target` as UTF-16 with a byte-order mark, which is what its first line
    declares. Printed and redirected instead, only PowerShell 5.1 happens to produce that; every other
    shell writes the bytes of its own code page under a declaration that says otherwise."""
    target.write_text(task_xml(window, **kwargs), encoding="utf-16", newline="\r\n")
    return target


def task_xml(window, *, python: Path | None = None, root: Path | None = None, user: str | None = None) -> str:
    """A task that starts the daemon every day when `window` (a `daemon.Window`) opens. The settings that
    are not Task Scheduler's defaults, and why:

    * **WakeToRun**: the machine is woken from sleep to run it (the user's choice, 2026-11-22). Windows
      honours this only where "Allow wake timers" is on in the power plan.
    * **StartWhenAvailable**: a start missed because the machine was off happens when it comes back, and
      the daemon itself ends at once if that is outside the window.
    * **No execution time limit**, and never "stop the task if it runs longer than": the task's "End" is
      a kill, which no handler sees. The daemon ends itself when its window closes.
    * **Batteries**: it starts on battery and keeps going; a night's work is the point.
    * **InteractiveToken**: only when the user is logged on, in their own session. The sandbox's
      AppContainer profile and grants have only ever been used that way.
    * **IgnoreNew**: a second start while one runs does nothing (the writers' lock would refuse it anyway).
    * **`pythonw.exe`**: no console window to close by accident. The record is the daemon's log in
      `data/daemon/`, and `oeisbot daemon --status` says what it is doing."""
    if window.always:
        raise ValueError("a scheduled task needs a window with an opening time; `always` has none")
    python = python or Path(sys.executable).with_name("pythonw.exe")
    root = root or config.ROOT
    user = user or os.environ.get("USERNAME", "")
    domain = os.environ.get("USERDOMAIN", "")
    account = f"{domain}\\{user}" if domain and user else user
    start = f"2026-01-01T{window.start_min // 60:02d}:{window.start_min % 60:02d}:00"
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>OEISBot: runs sessions unattended in the window {escape(str(window))} (local time). It submits nothing. Stop it with: oeisbot daemon --stop</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{start}</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{escape(account)}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>true</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(_quoted(python))}</Command>
      <Arguments>-m oeisbot.cli daemon --window {escape(str(window))}</Arguments>
      <WorkingDirectory>{escape(str(root))}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""
