"""The scheduled task that starts the daemon (item 58): a definition the user imports, nothing registered."""
from __future__ import annotations

import runpy
import sys
import xml.etree.ElementTree as ET

import pytest

from oeisbot import cli, config, daemon, lock, schedule
from oeisbot.daemon import Window

NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}


def test_the_task_wakes_the_machine_and_never_kills_the_daemon(tmp_path):
    xml = schedule.task_xml(Window.parse("22:00-08:00"), python=tmp_path / "venv & co" / "pythonw.exe",
                            root=tmp_path / "proj", user="someone")
    assert xml.startswith('<?xml version="1.0" encoding="UTF-16"?>')
    root = ET.fromstring(xml.split("?>", 1)[1])      # well formed, with the path's ampersand escaped

    def get(path):
        return root.find(path, NS).text

    assert get("t:Triggers/t:CalendarTrigger/t:StartBoundary").endswith("T22:00:00")
    assert get("t:Triggers/t:CalendarTrigger/t:ScheduleByDay/t:DaysInterval") == "1"
    settings = {e.tag.split("}")[1]: e.text for e in root.find("t:Settings", NS)}
    assert settings["WakeToRun"] == "true"                       # the user's choice
    assert settings["ExecutionTimeLimit"] == "PT0S"              # no limit: the task's "End" is a kill
    assert settings["StartWhenAvailable"] == "true" and settings["MultipleInstancesPolicy"] == "IgnoreNew"
    assert settings["DisallowStartIfOnBatteries"] == settings["StopIfGoingOnBatteries"] == "false"
    assert settings["RunOnlyIfIdle"] == "false" and settings["Enabled"] == "true"
    assert get("t:Principals/t:Principal/t:LogonType") == "InteractiveToken"
    assert get("t:Principals/t:Principal/t:RunLevel") == "LeastPrivilege"
    assert get("t:Principals/t:Principal/t:UserId").endswith("someone")
    # in quotes, because it has spaces: unquoted, Task Scheduler takes the rest for arguments
    assert get("t:Actions/t:Exec/t:Command") == '"' + str(tmp_path / "venv & co" / "pythonw.exe") + '"'
    plain = schedule.task_xml(Window.parse("22:00-08:00"), python=tmp_path.__class__("C:/venv/pythonw.exe"), user="u")
    assert f"<Command>{tmp_path.__class__('C:/venv/pythonw.exe')}</Command>" in plain            # and bare without
    assert get("t:Actions/t:Exec/t:Arguments") == "-m oeisbot.cli daemon --window 22:00-08:00"
    assert get("t:Actions/t:Exec/t:WorkingDirectory") == str(tmp_path / "proj")
    assert "It submits nothing" in get("t:RegistrationInfo/t:Description")


def test_the_task_starts_when_the_window_opens_whatever_the_window():
    assert schedule.task_xml(Window.parse("09:05-17:00"), user="u").count("T09:05:00") == 1
    assert "--window 09:05-17:00" in schedule.task_xml(Window.parse("9:05-17:00"), user="u")
    with pytest.raises(ValueError, match="needs a window with an opening time"):
        schedule.task_xml(Window.parse("always"))


def test_the_defaults_point_at_this_installation():
    xml = schedule.task_xml(Window.parse("22:00-08:00"), user="u")
    assert f"<WorkingDirectory>{config.ROOT}</WorkingDirectory>" in xml
    assert "pythonw.exe</Command>" in xml                        # no console window to close by accident


def test_the_definition_is_printed_and_nothing_is_started(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, "DATA", tmp_path / "data")
    monkeypatch.setattr(daemon.Daemon, "run", lambda self: pytest.fail("a night was started"))
    assert cli.main(["daemon", "--task-xml"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("<?xml") and "--window 22:00-08:00" in out and out.rstrip().endswith("</Task>")
    assert not lock.held() and not (tmp_path / "data").exists()  # it took no lock and wrote nothing
    assert cli.main(["daemon", "--task-xml", "--window", "23:30-06:00"]) == 0
    assert "T23:30:00" in capsys.readouterr().out
    # with a file name the file is written, in the encoding its first line declares
    target = tmp_path / "task.xml"
    assert cli.main(["daemon", "--task-xml", str(target)]) == 0
    said = capsys.readouterr().out
    assert f"wrote {target}" in said and 'schtasks /create /tn "OEISBot daemon" /xml' in said
    raw = target.read_bytes()
    assert raw[:2] == b"\xff\xfe"                              # UTF-16 little-endian, with its byte-order mark
    text = raw.decode("utf-16")
    assert text.startswith('<?xml version="1.0" encoding="UTF-16"?>') and "--window 22:00-08:00" in text
    assert "\r\n" in text and "\r\r\n" not in text
    ET.fromstring(raw)                                          # a parser that honours the declaration reads it
    with pytest.raises(SystemExit, match="needs a window with an opening time"):
        cli.main(["daemon", "--task-xml", "--window", "always"])
    with pytest.raises(SystemExit, match="expected HH:MM-HH:MM"):
        cli.main(["daemon", "--task-xml", "--window", "tonight"])


def test_the_command_the_task_runs_exists(tmp_path, monkeypatch, capsys):
    """The task runs `pythonw -m oeisbot.cli daemon ...`. Run the same module as a script, with a harmless
    argument, to pin that it reaches `main`."""
    monkeypatch.setattr(config, "DATA", tmp_path / "data")
    monkeypatch.setattr(sys, "argv", ["oeisbot", "daemon", "--status"])
    with pytest.raises(SystemExit) as done:
        runpy.run_module("oeisbot.cli", run_name="__main__")
    assert done.value.code == 0 and "daemon is not running" in capsys.readouterr().out
