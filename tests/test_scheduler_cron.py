"""Cron parser + ``next_after`` tests for the scheduler module
(Wave 97). Stdlib unittest only.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from backend.core.scheduler.cron import (
    CronParseError,
    SHORTCUTS,
    next_after,
    parse,
    validate,
)


class TestParseBasics(unittest.TestCase):
    def test_parse_wildcard(self) -> None:
        cron = parse("* * * * *")
        self.assertEqual(len(cron.minutes), 60)
        self.assertEqual(len(cron.hours), 24)
        self.assertEqual(len(cron.days), 31)
        self.assertEqual(len(cron.months), 12)
        self.assertEqual(len(cron.dows), 7)
        self.assertFalse(cron.dom_restricted)
        self.assertFalse(cron.dow_restricted)

    def test_parse_literal(self) -> None:
        cron = parse("0 9 * * 1-5")
        self.assertEqual(cron.minutes, frozenset({0}))
        self.assertEqual(cron.hours, frozenset({9}))
        # Mon..Fri
        self.assertEqual(cron.dows, frozenset({1, 2, 3, 4, 5}))
        self.assertTrue(cron.dow_restricted)
        self.assertFalse(cron.dom_restricted)

    def test_parse_step(self) -> None:
        cron = parse("*/15 * * * *")
        self.assertEqual(cron.minutes, frozenset({0, 15, 30, 45}))

    def test_parse_step_with_range(self) -> None:
        cron = parse("0-30/10 * * * *")
        self.assertEqual(cron.minutes, frozenset({0, 10, 20, 30}))

    def test_parse_list(self) -> None:
        cron = parse("0,15,30,45 * * * *")
        self.assertEqual(cron.minutes, frozenset({0, 15, 30, 45}))

    def test_parse_dow_names(self) -> None:
        cron = parse("0 9 * * MON")
        self.assertEqual(cron.dows, frozenset({1}))

    def test_parse_month_names(self) -> None:
        cron = parse("0 0 1 JAN *")
        self.assertEqual(cron.months, frozenset({1}))

    def test_parse_dow_seven_is_sunday(self) -> None:
        cron = parse("0 9 * * 7")
        # 7 normalises to 0 (Sun).
        self.assertEqual(cron.dows, frozenset({0}))


class TestParseShortcuts(unittest.TestCase):
    def test_hourly(self) -> None:
        cron = parse("@hourly")
        self.assertEqual(cron.minutes, frozenset({0}))
        self.assertEqual(len(cron.hours), 24)

    def test_daily(self) -> None:
        cron = parse("@daily")
        self.assertEqual(cron.minutes, frozenset({0}))
        self.assertEqual(cron.hours, frozenset({0}))

    def test_weekly(self) -> None:
        cron = parse("@weekly")
        self.assertEqual(cron.dows, frozenset({0}))

    def test_monthly(self) -> None:
        cron = parse("@monthly")
        self.assertEqual(cron.days, frozenset({1}))

    def test_unknown_shortcut_raises(self) -> None:
        with self.assertRaises(CronParseError):
            parse("@bogus")

    def test_shortcuts_constant_exposed(self) -> None:
        # All five families plus the two aliases.
        self.assertIn("@hourly", SHORTCUTS)
        self.assertIn("@daily", SHORTCUTS)
        self.assertIn("@weekly", SHORTCUTS)
        self.assertIn("@monthly", SHORTCUTS)
        self.assertIn("@yearly", SHORTCUTS)


class TestValidate(unittest.TestCase):
    def test_validate_good(self) -> None:
        self.assertTrue(validate("* * * * *"))
        self.assertTrue(validate("0 9 * * 1-5"))
        self.assertTrue(validate("@daily"))

    def test_validate_bad_field_count(self) -> None:
        self.assertFalse(validate("0 9 * *"))
        self.assertFalse(validate("0 9 * * 1 2"))

    def test_validate_bad_atom(self) -> None:
        self.assertFalse(validate("99 * * * *"))
        self.assertFalse(validate("0 25 * * *"))
        self.assertFalse(validate("0 0 0 * *"))
        self.assertFalse(validate("0 0 * 13 *"))
        self.assertFalse(validate("0 0 * * 8"))

    def test_validate_bad_step(self) -> None:
        self.assertFalse(validate("*/0 * * * *"))
        self.assertFalse(validate("*/-1 * * * *"))

    def test_validate_empty(self) -> None:
        self.assertFalse(validate(""))
        self.assertFalse(validate("   "))


class TestNextAfter(unittest.TestCase):
    """Deterministic ``next_after`` tests with fixed anchor times."""

    def test_every_minute_advances_one_minute(self) -> None:
        anchor = datetime(2026, 5, 10, 12, 30, tzinfo=timezone.utc)
        nxt = next_after("* * * * *", anchor)
        self.assertEqual(nxt, datetime(2026, 5, 10, 12, 31, tzinfo=timezone.utc))

    def test_weekday_9am_jumps_to_monday(self) -> None:
        # 2026-05-10 is a Sunday — next "weekday 9am" is Mon 2026-05-11 09:00.
        anchor = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)
        nxt = next_after("0 9 * * 1-5", anchor)
        self.assertEqual(nxt, datetime(2026, 5, 11, 9, 0, tzinfo=timezone.utc))

    def test_quarter_hour_step(self) -> None:
        anchor = datetime(2026, 5, 10, 12, 7, tzinfo=timezone.utc)
        nxt = next_after("*/15 * * * *", anchor)
        self.assertEqual(nxt, datetime(2026, 5, 10, 12, 15, tzinfo=timezone.utc))

    def test_yearly_jumps_to_jan(self) -> None:
        anchor = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)
        nxt = next_after("0 0 1 1 *", anchor)
        self.assertEqual(nxt, datetime(2027, 1, 1, 0, 0, tzinfo=timezone.utc))

    def test_daily_at_midnight(self) -> None:
        anchor = datetime(2026, 5, 10, 23, 30, tzinfo=timezone.utc)
        nxt = next_after("@daily", anchor)
        self.assertEqual(nxt, datetime(2026, 5, 11, 0, 0, tzinfo=timezone.utc))

    def test_strict_after_skips_current_minute(self) -> None:
        # Anchor exactly on a firing minute — next should be a step
        # later, not the same minute.
        anchor = datetime(2026, 5, 10, 0, 0, tzinfo=timezone.utc)
        nxt = next_after("@daily", anchor)
        self.assertEqual(nxt, datetime(2026, 5, 11, 0, 0, tzinfo=timezone.utc))

    def test_named_dow(self) -> None:
        # 2026-05-10 is Sun. Next MON 09:00.
        anchor = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)
        nxt = next_after("0 9 * * MON", anchor)
        self.assertEqual(nxt, datetime(2026, 5, 11, 9, 0, tzinfo=timezone.utc))


class TestNextAfterTimezone(unittest.TestCase):
    def test_la_9am_resolves_to_utc(self) -> None:
        # 09:00 America/Los_Angeles in May = 16:00 UTC (PDT, UTC-7).
        anchor = datetime(2026, 5, 10, 0, 0, tzinfo=timezone.utc)
        nxt = next_after("0 9 * * *", anchor, tz="America/Los_Angeles")
        # The next 09:00 LA after 2026-05-10 00:00 UTC (= 2026-05-09 17:00 LA)
        # is 2026-05-10 09:00 LA = 2026-05-10 16:00 UTC.
        self.assertEqual(nxt, datetime(2026, 5, 10, 16, 0, tzinfo=timezone.utc))

    def test_unknown_tz_raises(self) -> None:
        anchor = datetime(2026, 5, 10, 0, 0, tzinfo=timezone.utc)
        with self.assertRaises(CronParseError):
            next_after("0 9 * * *", anchor, tz="Mars/Olympus_Mons")


class TestVixieDomDowOr(unittest.TestCase):
    """When BOTH dom and dow are restricted, Vixie cron fires on
    either match."""

    def test_dom_or_dow_match(self) -> None:
        # "0 0 1 * 0" = midnight on the 1st of any month OR any Sun.
        cron = parse("0 0 1 * 0")
        # 2026-05-10 is Sun -> matches via dow.
        sun = datetime(2026, 5, 10, 0, 0, tzinfo=timezone.utc)
        self.assertTrue(cron.matches(sun))
        # 2026-06-01 is Mon -> matches via dom (1st).
        first = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
        self.assertTrue(cron.matches(first))
        # 2026-05-12 is Tue, not the 1st -> no match.
        nope = datetime(2026, 5, 12, 0, 0, tzinfo=timezone.utc)
        self.assertFalse(cron.matches(nope))


if __name__ == "__main__":
    unittest.main()
