"""Safety and scheduling checks; never send real desktop input."""

import argparse
import unittest
from unittest.mock import patch

import mouse_mover as app


class FakeClock:
    def __init__(self, stop_at=None):
        self.now = 0.0
        self.stop_at = stop_at

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds
        if self.stop_at is not None and self.now >= self.stop_at:
            raise KeyboardInterrupt


class FakeGUI:
    class FailSafeException(Exception):
        pass

    def __init__(self, clock=None, position=(100, 100)):
        self.clock = clock or FakeClock()
        self.cursor = position
        self.dimensions = (800, 600)
        self.moves = []
        self.presses = []
        self.corner_at = None
        self.user_moves = False
        self.press_error = None

    def failSafeCheck(self):
        if self.corner_at is not None and self.clock.now >= self.corner_at:
            raise self.FailSafeException

    def size(self):
        return self.dimensions

    def position(self):
        return self.cursor

    def moveTo(self, x, y, duration):
        self.moves.append(((x, y), duration, self.clock.now))
        self.cursor = (400, 400) if self.user_moves else (x, y)

    def press(self, key):
        self.presses.append((key, self.clock.now))
        if self.press_error is not None:
            raise self.press_error


class FakeControls:
    def __init__(self, busy=lambda: False):
        self.busy = busy
        self.releases = 0

    def input_busy(self):
        return self.busy()

    def release_shift(self):
        self.releases += 1


class MouseMoverTests(unittest.TestCase):
    def run_with_clock(self, gui, controls, interval=180, use_shift=True):
        with patch.object(app.time, "monotonic", gui.clock.monotonic), \
                patch.object(app.time, "sleep", gui.clock.sleep):
            app.run_loop(gui, controls, interval, use_shift)

    def test_continues_for_many_cycles_until_manual_interrupt(self):
        gui = FakeGUI(FakeClock(stop_at=1801))
        with self.assertRaises(KeyboardInterrupt):
            self.run_with_clock(gui, FakeControls())
        self.assertEqual(len(gui.presses), 10)
        self.assertEqual(len(gui.moves), 20)
        for index, (key, timestamp) in enumerate(gui.presses, start=1):
            self.assertEqual(key, "shift")
            self.assertAlmostEqual(timestamp, 180 * index, places=6)
        self.assertEqual(gui.cursor, (100, 100))

    def test_failsafe_exits_during_three_minute_wait(self):
        gui = FakeGUI()
        gui.corner_at = 0.6
        with self.assertRaises(gui.FailSafeException):
            self.run_with_clock(gui, FakeControls())
        self.assertLessEqual(gui.clock.now, 0.8)
        self.assertEqual(gui.moves, [])
        self.assertEqual(gui.presses, [])

    def test_all_four_current_primary_corners_stop(self):
        gui = FakeGUI()
        gui.dimensions = (1024, 768)
        for corner in ((0, 0), (1023, 0), (0, 767), (1023, 767)):
            with self.subTest(corner=corner):
                gui.cursor = corner
                with self.assertRaises(gui.FailSafeException):
                    app.check_stop(gui)

    def test_exactly_one_pixel_out_and_back_near_edges(self):
        corners = {(0, 0), (799, 0), (0, 599), (799, 599)}
        for origin in ((100, 100), (798, 0), (798, 599), (0, 1), (799, 1)):
            with self.subTest(origin=origin):
                gui = FakeGUI(position=origin)
                app.nudge_mouse(gui, FakeControls())
                target = gui.moves[0][0]
                distance = abs(target[0] - origin[0]) + abs(target[1] - origin[1])
                self.assertEqual(distance, 1)
                self.assertNotIn(target, corners)
                self.assertEqual(gui.cursor, origin)
                self.assertEqual(len(gui.moves), 2)

    def test_manual_mouse_movement_is_not_undone(self):
        gui = FakeGUI()
        gui.user_moves = True
        app.nudge_mouse(gui, FakeControls())
        self.assertEqual(len(gui.moves), 1)
        self.assertEqual(gui.cursor, (400, 400))

    def test_secondary_screen_pointer_is_not_repositioned(self):
        gui = FakeGUI(position=(-200, 100))
        app.nudge_mouse(gui, FakeControls())
        self.assertEqual(gui.moves, [])
        self.assertEqual(gui.cursor, (-200, 100))

    def test_held_buttons_defer_activity_until_release(self):
        gui = FakeGUI(FakeClock(stop_at=181))
        controls = FakeControls(busy=lambda: gui.clock.now < 180.6)
        with self.assertRaises(KeyboardInterrupt):
            self.run_with_clock(gui, controls)
        self.assertEqual(len(gui.presses), 1)
        self.assertGreaterEqual(gui.presses[0][1], 180.6)

    def test_mouse_only_mode_sends_no_keys(self):
        gui = FakeGUI(FakeClock(stop_at=361))
        with self.assertRaises(KeyboardInterrupt):
            self.run_with_clock(gui, FakeControls(), use_shift=False)
        self.assertEqual(len(gui.moves), 4)
        self.assertEqual(gui.presses, [])

    def test_interrupted_shift_is_released_and_exception_propagates(self):
        for error in (KeyboardInterrupt(), FakeGUI.FailSafeException()):
            with self.subTest(error=type(error).__name__):
                gui = FakeGUI()
                gui.press_error = error
                controls = FakeControls()
                with self.assertRaises(type(error)):
                    app.tap_shift(gui, controls)
                self.assertEqual(controls.releases, 1)

    def test_manual_stop_has_clean_exit_and_errors_remain_visible(self):
        for error, expected in (
            (KeyboardInterrupt(), 0),
            (FakeGUI.FailSafeException(), 0),
            (RuntimeError("test failure"), 1),
        ):
            with self.subTest(error=type(error).__name__):
                with patch.dict("sys.modules", {"pyautogui": FakeGUI()}), \
                        patch.object(app.sys, "platform", "win32"), \
                        patch.object(app, "WindowsControls", return_value=FakeControls()), \
                        patch.object(app, "run_loop", side_effect=error), \
                        self.assertLogs(app.LOG, level="INFO") as messages:
                    self.assertEqual(app.main([]), expected)
                self.assertTrue(any("Stopped" in message for message in messages.output))

    def test_invalid_intervals_are_rejected(self):
        for value in ("0", "-1", "nan", "inf", "abc", "9"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    app.interval_seconds(value)
        self.assertEqual(app.interval_seconds("180"), 180)


if __name__ == "__main__":
    unittest.main()
