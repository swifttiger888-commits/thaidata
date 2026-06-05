#!/usr/bin/env python3
"""Tests for health_check.py — uptime, data freshness, CI status, Telegram alerts."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from health_check import (
    check_uptime,
    check_data_freshness,
    check_ci_status,
    send_telegram_alert,
)


class TestCheckUptime(unittest.TestCase):
    """Tests for check_uptime()."""

    @patch("urllib.request.urlopen")
    def test_site_up(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        result = check_uptime()
        self.assertIsNone(result)

    @patch("urllib.request.urlopen")
    def test_site_down_500(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        result = check_uptime()
        self.assertIn("500", result or "")

    @patch("urllib.request.urlopen")
    def test_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Connection refused")
        result = check_uptime()
        self.assertIn("Connection refused", result or "")


class TestCheckDataFreshness(unittest.TestCase):
    """Tests for check_data_freshness()."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json")
        self.tmp_path = self.tmp.name

    def tearDown(self):
        os.unlink(self.tmp_path)

    def _write_data(self, updated_str):
        json.dump({"updated": updated_str, "restaurants": []}, self.tmp)
        self.tmp.close()

    def test_fresh_data(self):
        today_str = date.today().isoformat()
        self._write_data(today_str)
        with patch("health_check.DATA_FILE", self.tmp_path):
            result = check_data_freshness()
        self.assertIsNone(result)

    def test_stale_data(self):
        old = (date.today() - timedelta(days=10)).isoformat()
        self._write_data(old)
        with patch("health_check.DATA_FILE", self.tmp_path):
            result = check_data_freshness()
        self.assertIsNotNone(result)
        self.assertIn("10 days old", result or "")

    def test_data_at_boundary(self):
        just_ok = (date.today() - timedelta(days=8)).isoformat()
        self._write_data(just_ok)
        with patch("health_check.DATA_FILE", self.tmp_path):
            result = check_data_freshness()
        self.assertIsNone(result)

    def test_missing_file(self):
        with patch("health_check.DATA_FILE", "/nonexistent/file.json"):
            result = check_data_freshness()
        self.assertIsNotNone(result)
        self.assertIn("not found", result or "")

    def test_no_updated_field(self):
        json.dump({"restaurants": []}, self.tmp)
        self.tmp.close()
        with patch("health_check.DATA_FILE", self.tmp_path):
            result = check_data_freshness()
        self.assertIsNotNone(result)
        self.assertIn("No 'updated' field", result or "")

    def test_invalid_date_format(self):
        self._write_data("not-a-date")
        with patch("health_check.DATA_FILE", self.tmp_path):
            result = check_data_freshness()
        self.assertIsNotNone(result)
        self.assertIn("Invalid date format", result or "")

    def test_broken_json(self):
        with open(self.tmp_path, "w") as f:
            f.write("{broken json")
        with patch("health_check.DATA_FILE", self.tmp_path):
            result = check_data_freshness()
        self.assertIsNotNone(result)
        self.assertIn("Cannot read", result or "")


class TestCheckCiStatus(unittest.TestCase):
    """Tests for check_ci_status()."""

    def setUp(self):
        self.mock_token = "ghp_fake_token"

    @patch.dict(os.environ, {}, clear=True)
    def test_token_missing(self):
        result = check_ci_status()
        self.assertIsNotNone(result)
        self.assertIn("not set", result or "")

    @patch("urllib.request.urlopen")
    def test_ci_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "workflow_runs": [
                {"run_number": 42, "conclusion": "success", "html_url": ""}
            ]
        }).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        with patch.dict(os.environ, {"GITHUB_TOKEN": self.mock_token}):
            result = check_ci_status()
        self.assertIsNone(result)

    @patch("urllib.request.urlopen")
    def test_ci_failed(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "workflow_runs": [
                {"run_number": 41, "conclusion": "failure", "html_url": "https://..."}
            ]
        }).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        with patch.dict(os.environ, {"GITHUB_TOKEN": self.mock_token}):
            result = check_ci_status()
        self.assertIsNotNone(result)
        self.assertIn("failure", result or "")

    @patch("urllib.request.urlopen")
    def test_ci_empty_runs(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"workflow_runs": []}).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        with patch.dict(os.environ, {"GITHUB_TOKEN": self.mock_token}):
            result = check_ci_status()
        self.assertIsNotNone(result)
        self.assertIn("No completed CI runs", result or "")

    @patch("urllib.request.urlopen")
    def test_ci_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("API rate limit exceeded")
        with patch.dict(os.environ, {"GITHUB_TOKEN": self.mock_token}):
            result = check_ci_status()
        self.assertIsNotNone(result)
        self.assertIn("CI status check failed", result or "")


class TestSendTelegramAlert(unittest.TestCase):
    """Tests for send_telegram_alert()."""

    @patch("urllib.request.urlopen")
    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}, clear=True)
    def test_no_token_or_chat(self, mock_urlopen):
        """Silent when no token/chat configured — no API call made."""
        send_telegram_alert(["test error"])
        mock_urlopen.assert_not_called()

    @patch("urllib.request.urlopen")
    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "bot123", "TELEGRAM_CHAT_ID": ""}, clear=True)
    def test_no_chat_id(self, mock_urlopen):
        """Silent when no chat ID configured."""
        send_telegram_alert(["test error"])
        mock_urlopen.assert_not_called()

    @patch("urllib.request.urlopen")
    @patch.dict(
        os.environ,
        {"TELEGRAM_BOT_TOKEN": "bot123", "TELEGRAM_CHAT_ID": "chat456"},
        clear=True,
    )
    def test_sends_alert(self, mock_urlopen):
        """Sends message when both token and chat ID are configured."""
        send_telegram_alert(["Server down", "Data stale"])
        mock_urlopen.assert_called_once()
        # Verify the API URL
        url = mock_urlopen.call_args[0][0].full_url
        self.assertIn("api.telegram.org/botbot123/sendMessage", url)

    @patch("urllib.request.urlopen")
    @patch.dict(
        os.environ,
        {"TELEGRAM_BOT_TOKEN": "bot123", "TELEGRAM_CHAT_ID": "chat456"},
        clear=True,
    )
    def test_network_error_does_not_crash(self, mock_urlopen):
        """Network error during Telegram send should not raise."""
        mock_urlopen.side_effect = Exception("Timeout")
        send_telegram_alert(["test"])  # Should print warning, not crash


if __name__ == "__main__":
    unittest.main()
