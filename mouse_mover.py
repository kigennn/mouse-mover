"""Keep a Windows desktop active until the user stops this terminal app."""

import argparse
import ctypes
import logging
import math
import sys
import time


DEFAULT_INTERVAL = 180.0
POLL_INTERVAL = 0.2
MOVE_DURATION = 0.15
LOG = logging.getLogger("mouse_mover")


class WindowsControls:
    """Read held buttons and release Shift if a tap is interrupted."""

    # Mouse buttons, Shift, Ctrl, Alt, and the two Windows keys.
    HELD_KEYS = (0x01, 0x02, 0x04, 0x05, 0x06, 0x10, 0x11, 0x12, 0x5B, 0x5C)

    def __init__(self):
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
        self.user32.GetAsyncKeyState.restype = ctypes.c_short
        self.user32.keybd_event.argtypes = (
            ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_ulong, ctypes.c_size_t
        )
        self.user32.keybd_event.restype = None

    def input_busy(self):
        return any(self.user32.GetAsyncKeyState(key) & 0x8000 for key in self.HELD_KEYS)

    def release_shift(self):
        # Cleanup only: KEYEVENTF_KEYUP, matching PyAutoGUI's Shift virtual key.
        # This works even when the cursor failsafe blocks PyAutoGUI calls.
        self.user32.keybd_event(0x10, 0, 0x0002, 0)


def check_stop(gui):
    """Check corners during the wait, including after a resolution change."""
    gui.failSafeCheck()
    width, height = gui.size()
    corners = {(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)}
    if tuple(gui.position()) in corners:
        raise gui.FailSafeException("Pointer reached a corner of the primary screen.")


def nudge_mouse(gui, controls):
    """Move one pixel and return, without targeting an edge corner."""
    check_stop(gui)
    original = tuple(gui.position())
    x, y = original
    width, height = gui.size()
    if not (0 <= x < width and 0 <= y < height):
        return "Mouse outside primary screen; movement skipped"

    corners = {(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)}
    candidates = ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
    target = next(
        (point for point in candidates
         if 0 <= point[0] < width and 0 <= point[1] < height and point not in corners),
        None,
    )
    if target is None or controls.input_busy():
        return "Mouse movement deferred"

    gui.moveTo(*target, duration=MOVE_DURATION)
    check_stop(gui)
    # Avoid pulling the pointer back if the user moved it during the nudge.
    if tuple(gui.position()) == target and not controls.input_busy():
        gui.moveTo(*original, duration=MOVE_DURATION)
        return "Mouse moved 1 pixel and returned"
    return "Mouse moved 1 pixel; user activity detected, return skipped"


def tap_shift(gui, controls):
    """Tap Shift, with emergency key release if the tap is interrupted."""
    try:
        gui.press("shift")
    except BaseException:
        controls.release_shift()
        raise


def run_loop(gui, controls, interval=DEFAULT_INTERVAL, use_shift=True):
    """Run indefinitely; only a stop request or an error exits this loop."""
    next_action = time.monotonic() + interval
    while True:
        check_stop(gui)
        now = time.monotonic()
        remaining = next_action - now
        if remaining > 0:
            time.sleep(min(POLL_INTERVAL, remaining))
            continue
        if controls.input_busy():
            time.sleep(POLL_INTERVAL)
            continue

        # Schedule from this cycle; never send a burst of overdue events.
        next_action = now + interval
        message = nudge_mouse(gui, controls)
        if use_shift and not controls.input_busy():
            check_stop(gui)
            tap_shift(gui, controls)
            message += "; Shift tapped and released"
        LOG.info(message)


def interval_seconds(value):
    try:
        interval = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use a number of seconds, such as 180.") from exc
    if not math.isfinite(interval) or interval < 10:
        raise argparse.ArgumentTypeError("The interval must be at least 10 seconds.")
    return interval


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Move the mouse 1 pixel out and back, and tap Shift, indefinitely."
    )
    parser.add_argument(
        "--interval", type=interval_seconds, default=DEFAULT_INTERVAL,
        metavar="SECONDS", help="activity interval in seconds (default: 180; minimum: 10)",
    )
    parser.add_argument("--no-shift", action="store_true", help="use mouse movements only")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")

    if sys.platform != "win32":
        LOG.error("This app is intended for Windows.")
        return 1

    try:
        import pyautogui
    except ImportError:
        LOG.error("PyAutoGUI is missing. Run start.cmd to install the dependencies.")
        return 1

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1
    LOG.info("Mouse Mover running continuously. There is no time limit.")
    LOG.info("Activity every %g seconds; Shift %s.", args.interval, "off" if args.no_shift else "on")
    LOG.info("Stop: close this terminal, press Ctrl+C, or move into any primary-screen corner.")
    LOG.info("First activity in %g seconds. Keep this terminal open; it can be minimized.", args.interval)

    try:
        run_loop(pyautogui, WindowsControls(), args.interval, not args.no_shift)
    except pyautogui.FailSafeException:
        LOG.info("Stopped: mouse corner failsafe triggered.")
    except KeyboardInterrupt:
        LOG.info("Stopped: Ctrl+C pressed.")
    except Exception as exc:
        LOG.error("Stopped because of an error: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
