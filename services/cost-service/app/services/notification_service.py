"""
CloudPulse AI - Cost Service
Notification service for delivering alerts via Slack, Teams, and webhooks.
"""
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class NotificationService:
    """Dispatch alert payloads to configured notification channels."""

    async def send(
        self,
        channel_type: str,
        config: dict,
        event_type: str,
        payload: dict[str, Any],
    ) -> bool:
        """
        Route the notification to the correct formatter and deliver it.
        Returns True on successful delivery.
        """
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            logger.error("Notification channel missing webhook_url")
            return False

        try:
            if channel_type == "slack":
                body = self._format_slack(event_type, payload)
            elif channel_type == "teams":
                body = self._format_teams(event_type, payload)
            else:
                body = self._format_webhook(event_type, payload)

            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.post(webhook_url, json=body)
                resp.raise_for_status()

            logger.info(f"Notification sent via {channel_type}: {event_type}")
            return True

        except httpx.HTTPStatusError as exc:
            logger.error(f"Notification HTTP error ({channel_type}): {exc.response.status_code}")
            return False
        except Exception as exc:
            logger.error(f"Notification delivery failed ({channel_type}): {exc}")
            return False

    async def send_test(self, channel_type: str, config: dict) -> bool:
        """Send a test notification to verify the channel is working."""
        return await self.send(
            channel_type=channel_type,
            config=config,
            event_type="test",
            payload={
                "title": "CloudPulse Test Notification",
                "message": "If you see this, your notification channel is working!",
            },
        )

    # ------------------------------------------------------------------
    # Slack Block Kit formatting
    # ------------------------------------------------------------------

    def _format_slack(self, event_type: str, payload: dict) -> dict:
        title = payload.get("title", f"CloudPulse Alert: {event_type}")
        message = payload.get("message", "")
        color = self._severity_color(payload.get("severity", "info"))

        blocks: list[dict] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"⚡ {title}", "emoji": True},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message},
            },
        ]

        # Add detail fields if present
        fields = payload.get("fields")
        if fields and isinstance(fields, dict):
            field_blocks = []
            for k, v in fields.items():
                field_blocks.append({"type": "mrkdwn", "text": f"*{k}*\n{v}"})
            blocks.append({"type": "section", "fields": field_blocks[:10]})

        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"CloudPulse AI • {event_type} • {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
                },
            ],
        })

        return {
            "blocks": blocks,
            "attachments": [{"color": color, "blocks": []}],
        }

    # ------------------------------------------------------------------
    # Teams Adaptive Card formatting
    # ------------------------------------------------------------------

    def _format_teams(self, event_type: str, payload: dict) -> dict:
        title = payload.get("title", f"CloudPulse Alert: {event_type}")
        message = payload.get("message", "")
        color = self._severity_color(payload.get("severity", "info"))

        facts = []
        fields = payload.get("fields")
        if fields and isinstance(fields, dict):
            facts = [{"title": k, "value": str(v)} for k, v in fields.items()]

        card = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {
                                "type": "TextBlock",
                                "size": "Large",
                                "weight": "Bolder",
                                "text": f"⚡ {title}",
                                "color": "Attention" if color == "#e74c3c" else "Default",
                            },
                            {"type": "TextBlock", "text": message, "wrap": True},
                            *(
                                [
                                    {
                                        "type": "FactSet",
                                        "facts": facts,
                                    }
                                ]
                                if facts
                                else []
                            ),
                            {
                                "type": "TextBlock",
                                "text": f"CloudPulse AI • {event_type} • {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
                                "size": "Small",
                                "isSubtle": True,
                            },
                        ],
                    },
                }
            ],
        }
        return card

    # ------------------------------------------------------------------
    # Generic webhook
    # ------------------------------------------------------------------

    def _format_webhook(self, event_type: str, payload: dict) -> dict:
        return {
            "event": event_type,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            **payload,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _severity_color(severity: str) -> str:
        return {
            "critical": "#e74c3c",
            "high": "#e67e22",
            "medium": "#f1c40f",
            "low": "#3498db",
            "info": "#2ecc71",
        }.get(severity, "#95a5a6")


# Convenience helpers for worker integration

def build_anomaly_payload(
    anomaly: dict[str, Any],
    account_name: str = "",
) -> dict[str, Any]:
    """Build a notification payload for an anomaly event."""
    severity = anomaly.get("severity", "medium")
    service = anomaly.get("service", "Unknown")
    actual = anomaly.get("actual_amount") or anomaly.get("actual_cost", 0)
    expected = anomaly.get("expected_amount") or anomaly.get("expected_cost", 0)
    deviation = anomaly.get("deviation_percent", 0)

    return {
        "title": f"Cost Anomaly Detected — {severity.upper()}",
        "message": f"Unusual spending detected on *{service}* in account *{account_name}*.",
        "severity": severity,
        "fields": {
            "Service": service,
            "Account": account_name or "N/A",
            "Actual Cost": f"${float(actual):,.2f}",
            "Expected Cost": f"${float(expected):,.2f}",
            "Deviation": f"{float(deviation):+.1f}%",
            "Severity": severity.capitalize(),
        },
    }


def build_budget_payload(
    budget_name: str,
    usage_percent: float,
    current_spend: float,
    budget_amount: float,
    threshold: int,
) -> dict[str, Any]:
    """Build a notification payload for a budget threshold event."""
    return {
        "title": f"Budget Alert — {budget_name}",
        "message": f"Budget *{budget_name}* has reached *{usage_percent:.0f}%* of its limit.",
        "severity": "critical" if threshold >= 100 else "high" if threshold >= 80 else "medium",
        "fields": {
            "Budget": budget_name,
            "Current Spend": f"${current_spend:,.2f}",
            "Budget Limit": f"${budget_amount:,.2f}",
            "Usage": f"{usage_percent:.1f}%",
            "Threshold Crossed": f"{threshold}%",
        },
    }


def build_sync_failure_payload(
    account_name: str,
    provider: str,
    error: str,
) -> dict[str, Any]:
    """Build a notification payload for a sync failure event."""
    return {
        "title": f"Sync Failed — {account_name}",
        "message": f"Cost sync for *{account_name}* ({provider}) failed.",
        "severity": "high",
        "fields": {
            "Account": account_name,
            "Provider": provider,
            "Error": error[:200],
        },
    }


# Singleton
_notification_service: NotificationService | None = None


def get_notification_service() -> NotificationService:
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
