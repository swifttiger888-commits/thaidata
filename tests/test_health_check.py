#!/usr/bin/env python3
"""Tests for health_check.py — uptime and data freshness checks."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from health_check import check_uptime, check_data_freshness


class TestCheckUptime(unittest.TestCase):
    """Tests for check_uptime()."""

    @patch('urllib.request.urlopen')
    def test_site_up(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        result = check_uptime()
        self.assertIsNone(result)

    @patch('urllib.request.urlopen')
    def test_site_down_500(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        result = check_uptime()
        self.assertIn("500", result or "")

    @patch('urllib.request.urlopen')
    def test_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Connection refused")
        result = check_uptime()
        self.assertIn("Connection refused", result or "")


class TestCheckDataFreshness(unittest.TestCase):
    """Tests for check_data_freshness()."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.tmp_path = self.tmp.name

    def tearDown(self):
        os.unlink(self.tmp_path)

    def _write_data(self, updated_str):
        json.dump({"updated": updated_str, "restaurants": []}, self.tmp)
        self.tmp.close()

    def test_fresh_data(self):
        today_str = date.today().isoformat()
        self._write_data(today_str)
        with patch('health_check.DATA_FILE', self.tmp_path):
            result = check_data_freshness()
        self.assertIsNone(result)

    def test_stale_data(self):
        old = (date.today() - timedelta(days=10)).isoformat()
        self._write_data(old)
        with patch('health_check.DATA_FILE', self.tmp_path):
            result = check_data_freshness()
        self.assertIsNotNone(result)
        self.assertIn("10 days old", result or "")

    def test_data_at_boundary(self):
        just_ok = (date.today() - timedelta(days=8)).isoformat()
        self._write_data(just_ok)
        with patch('health_check.DATA_FILE', self.tmp_path):
            result = check_data_freshness()
        self.assertIsNone(result)

    def test_missing_file(self):
        with patch('health_check.DATA_FILE', '/nonexistent/file.json'):
            result = check_data_freshness()
        self.assertIsNotNone(result)
        self.assertIn("not found", result or "")

    def test_no_updated_field(self):
        json.dump({"restaurants": []}, self.tmp)
        self.tmp.close()
        with patch('health_check.DATA_FILE', self.tmp_path):
            result = check_data_freshness()
        self.assertIsNotNone(result)
        self.assertIn("No 'updated' field", result or "")

    def test_invalid_date_format(self):
        self._write_data("not-a-date")
        with patch('health_check.DATA_FILE', self.tmp_path):
            result = check_data_freshness()
        self.assertIsNotNone(result)
        self.assertIn("Invalid date format", result or "")

    def test_broken_json(self):
        with open(self.tmp_path, 'w') as f:
            f.write("{broken json")
        with patch('health_check.DATA_FILE', self.tmp_path):
            result = check_data_freshness()
        self.assertIsNotNone(result)
        self.assertIn("Cannot read", result or "")


if __name__ == '__main__':
    unittest.main()
