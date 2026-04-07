"""
CloudPulse AI - Cost Service
Tests for the notification service.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.services.notification_service import (
    NotificationService,
    build_anomaly_payload,
    build_budget_payload,
    build_sync_failure_payload,
)


class TestNotificationFormatting:
    """Tests for notification payload formatting."""

    def setup_method(self):
        self.svc = NotificationService()

    def test_format_slack(self):
        body = self.svc._format_slack("anomaly", {
            "title": "Cost Spike",
            "message": "EC2 costs jumped",
            "severity": "high",
            "fields": {"Service": "EC2", "Cost": "$500"},
        })
        assert "blocks" in body
        assert body["blocks"][0]["type"] == "header"

    def test_format_teams(self):
        body = self.svc._format_teams("budget", {
            "title": "Budget Alert",
            "message": "80% reached",
            "fields": {"Budget": "Prod", "Usage": "80%"},
        })
        assert body["type"] == "message"
        assert "attachments" in body
        card = body["attachments"][0]["content"]
        assert card["type"] == "AdaptiveCard"

    def test_format_webhook(self):
        body = self.svc._format_webhook("sync_failure", {
            "title": "Sync Failed",
            "message": "API error",
        })
        assert body["event"] == "sync_failure"
        assert "timestamp" in body
        assert body["title"] == "Sync Failed"

    def test_severity_color(self):
        assert NotificationService._severity_color("critical") == "#e74c3c"
        assert NotificationService._severity_color("low") == "#3498db"
        assert NotificationService._severity_color("unknown") == "#95a5a6"


class TestPayloadBuilders:
    """Tests for convenience payload builder functions."""

    def test_anomaly_payload(self):
        payload = build_anomaly_payload(
            {"severity": "high", "service": "EC2", "actual_amount": 500, "expected_amount": 100, "deviation_percent": 400},
            account_name="prod-aws",
        )
        assert payload["severity"] == "high"
        assert "EC2" in payload["message"]
        assert "prod-aws" in payload["message"]
        assert "Service" in payload["fields"]

    def test_budget_payload(self):
        payload = build_budget_payload("Monthly Prod", 85.0, 8500, 10000, 80)
        assert "Monthly Prod" in payload["title"]
        assert payload["severity"] == "high"
        assert "80%" in payload["fields"]["Threshold Crossed"]

    def test_budget_payload_critical(self):
        payload = build_budget_payload("Quarterly", 102.0, 10200, 10000, 100)
        assert payload["severity"] == "critical"

    def test_sync_failure_payload(self):
        payload = build_sync_failure_payload("prod-aws", "aws", "Unauthorized")
        assert payload["severity"] == "high"
        assert "prod-aws" in payload["message"]
        assert "Unauthorized" in payload["fields"]["Error"]


class TestNotificationSend:
    """Tests for the send method."""

    @pytest.mark.asyncio
    async def test_send_missing_webhook_url(self):
        svc = NotificationService()
        result = await svc.send("slack", {}, "test", {"title": "test"})
        assert result is False

    @pytest.mark.asyncio
    async def test_send_success(self):
        svc = NotificationService()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = lambda: None

        with patch("app.services.notification_service.httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.post = AsyncMock(return_value=mock_response)
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = client_instance

            result = await svc.send("slack", {"webhook_url": "https://hooks.slack.com/test"}, "anomaly", {"title": "Test"})
            assert result is True

    @pytest.mark.asyncio
    async def test_send_test_message(self):
        svc = NotificationService()
        svc.send = AsyncMock(return_value=True)  # type: ignore[method-assign]
        result = await svc.send_test("slack", {"webhook_url": "https://hooks.slack.com/test"})
        assert result is True
