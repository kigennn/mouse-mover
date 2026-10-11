# Mouse Mover for Windows

A visible terminal app for long local processing tasks. It runs indefinitely,
with no timeout or cycle limit, until you stop it. Every 180 seconds it moves the
mouse one pixel and back over short, gentle movements, then taps and releases
Shift. The first activity happens three minutes after launch.

## Start

Double-click `start.cmd`. It uses the Python installation on your computer,
creates a local `.venv`, installs PyAutoGUI if needed, and runs the app. The first
setup needs internet access. After setup, the app can run offline.

Or open PowerShell in this folder and run:

```powershell
.\start.cmd
```

Keep its terminal open. You can minimize it while processing continues.
The app does not start automatically with Windows.

## Stop manually

- Close the terminal window containing the app.
- Press **Ctrl+C** in that terminal.
- Move the pointer all the way into **any corner of the primary screen**.
  The app checks for this about every 0.2 seconds, including while waiting
  between movements, and exits. Move away from the corner before restarting.

The [PyAutoGUI corner failsafe](https://pyautogui.readthedocs.io/en/latest/index.html#fail-safes)
stays enabled. Nothing restarts the app after you stop it.

## Options

Mouse movements only:

```powershell
.\start.cmd --no-shift
```

A different interval, in seconds (minimum 10):

```powershell
.\start.cmd --interval 120
```

Once dependencies are installed, you can run the Python script directly:

```powershell
.\.venv\Scripts\python.exe -u .\mouse_mover.py
```

## Behavior and limits

- Activity is deferred while a mouse button, Shift, Ctrl, Alt, or a Windows key
  is held. The pointer is not pulled back if it moves during the nudge.
- Shift reaches the currently focused app and can affect some apps. Use
  `--no-shift` if that is a concern. It is a single tap every cycle, not a hold
  or a rapid series of taps.
- PyAutoGUI supports the primary screen. Mouse movement is skipped when the
  pointer is on another screen; Shift can still be tapped. The corner stop
  gesture uses the primary screen.
- This generates ordinary input; it does not change Windows power or lock
  settings. It may reduce ordinary idle locking, but cannot guarantee that
  every Windows or organization-enforced lock rule accepts simulated input.
  A lock timeout shorter than the configured interval can still expire.
- Sleep, hibernation, a locked desktop, or signing out can interrupt input.
  Unexpected errors are shown in the terminal and stop the app.

## Verification

The tests use simulated input and a simulated clock, so they do not move your
real mouse or press keys:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

References: [PyAutoGUI keyboard controls](https://pyautogui.readthedocs.io/en/latest/keyboard.html)
and [supported screens and focused-window input](https://pypi.org/project/PyAutoGUI/).
