from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "sync_schedule", Path(__file__).resolve().parents[1] / "scripts" / "sync_schedule.py"
)
schedule = importlib.util.module_from_spec(spec)
spec.loader.exec_module(schedule)


class ScheduleTests(unittest.TestCase):
    def test_alternating_dates(self):
        for day, expected in ((28, True), (29, False), (30, True), (31, False)):
            with self.subTest(day=day):
                now = datetime(2026, 10, day, 5, tzinfo=timezone.utc)
                self.assertEqual(schedule.is_due("schedule", now), expected)

    def test_every_48_hours_across_month_year_and_dst_boundaries(self):
        start = datetime(2026, 10, 28, 5, tzinfo=timezone.utc)
        due = [start + timedelta(days=day) for day in range(800)
               if schedule.is_due("schedule", start + timedelta(days=day))]
        self.assertEqual(len(due), 400)
        self.assertTrue(all(b - a == timedelta(hours=48) for a, b in zip(due, due[1:])))
        cet = timezone(timedelta(hours=1))
        self.assertTrue(all(now.astimezone(cet).hour == 6 for now in due))

    def test_manual_run_bypasses_off_day(self):
        self.assertTrue(schedule.is_due(
            "workflow_dispatch", datetime(2026, 10, 29, 5, tzinfo=timezone.utc)
        ))

    def test_non_schedule_event_does_not_run(self):
        self.assertFalse(schedule.is_due(
            "pull_request", datetime(2026, 10, 28, 5, tzinfo=timezone.utc)
        ))

    def test_dates_are_evaluated_in_utc(self):
        now = datetime(2026, 10, 29, 1, tzinfo=timezone(timedelta(hours=3)))
        self.assertTrue(schedule.is_due("schedule", now))

    def test_naive_datetimes_are_rejected(self):
        with self.assertRaises(ValueError):
            schedule.is_due("schedule", datetime(2026, 10, 28, 5))


if __name__ == "__main__":
    unittest.main()
