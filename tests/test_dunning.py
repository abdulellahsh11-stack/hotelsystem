#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_dunning.py — إعادة محاولة رسائل الديون (بند: منطق إعادة المحاولة).

تحقّقٌ بالكسر: جدول التراجع الأسّي المُقيَّد (٢٤·٤٨·٩٦·١٦٨ بسقف ١٦٨)،
توقّف `should_retry` بعد الحدّ الأقصى، وتصاعد نبرة الرسالة عبر المحاولات.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import dunning  # noqa: E402


class TestNextAttempt:
    def test_backoff_schedule(self):
        assert dunning.next_attempt(1) == 24
        assert dunning.next_attempt(2) == 48
        assert dunning.next_attempt(3) == 96
        assert dunning.next_attempt(4) == 168   # ١٩٢ مقصوصةً عند السقف

    def test_capped_at_max(self):
        assert dunning.next_attempt(9) == 168
        assert dunning.next_attempt(20, max_hours=168) == 168

    def test_custom_base(self):
        assert dunning.next_attempt(1, base_hours=6) == 6
        assert dunning.next_attempt(2, base_hours=6) == 12

    def test_non_positive_treated_as_first(self):
        assert dunning.next_attempt(0) == 24
        assert dunning.next_attempt(-3) == 24


class TestShouldRetry:
    def test_stops_after_max(self):
        assert dunning.should_retry(0) is True
        assert dunning.should_retry(3) is True
        assert dunning.should_retry(4) is False   # بلغ الحدّ
        assert dunning.should_retry(5) is False

    def test_custom_max(self):
        assert dunning.should_retry(1, max_attempts=2) is True
        assert dunning.should_retry(2, max_attempts=2) is False


class TestDunningMessage:
    def test_escalates_across_attempts(self):
        s1 = dunning.dunning_message({"name": "X"}, 1, lang="ar")["subject"]
        s2 = dunning.dunning_message({"name": "X"}, 2, lang="ar")["subject"]
        s4 = dunning.dunning_message({"name": "X"}, 4, lang="ar")["subject"]
        assert s1 != s2 != s4
        assert s1 != s4
        # المحاولة الأخيرة تحمل نبرة الإنذار الأخير
        assert "أخير" in s4

    def test_beyond_table_uses_last_tone(self):
        last = dunning.dunning_message({"name": "X"}, 4, lang="ar")["subject"]
        beyond = dunning.dunning_message({"name": "X"}, 9, lang="ar")["subject"]
        assert beyond == last

    def test_ar_and_en_differ(self):
        ar = dunning.dunning_message({"name": "X"}, 1, lang="ar")
        en = dunning.dunning_message({"name": "X"}, 1, lang="en")
        assert ar["subject"] != en["subject"]
        assert "Hello X" in en["body_text"]

    def test_client_name_escaped(self):
        msg = dunning.dunning_message({"name": "<b>x</b>"}, 1, lang="en")
        assert "<b>" not in msg["body_text"]
        assert "&lt;b&gt;" in msg["body_text"]

    def test_default_name_when_missing(self):
        msg = dunning.dunning_message({}, 1, lang="en")
        assert "Dear customer" in msg["body_text"]
