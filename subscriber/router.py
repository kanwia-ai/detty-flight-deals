"""
Detty Flight Deals - Alert Router
Routes deals to the correct subscribers based on tier and metro preferences.

Routing logic:
  - Free tier: Great deals queued for weekly digest
  - Premium/trial: ALL deals sent instantly (Great + WOW + mistake)
  - Mistake fares: SMS alert to premium subscribers with phone numbers
  - WOW/mistake deals: Also queued as FOMO teasers for free tier digest

Usage:
    from subscriber.router import AlertRouter

    router = AlertRouter()
    result = router.route_deal(deal)
    # {"instant_emails": 2, "sms_sent": 1, "digest_queued": True, "skipped_limit": False}
"""

import json
import logging
import time
from typing import Optional

from db.client import TursoClient
from subscriber.manager import SubscriberManager
from subscriber.metro_groups import airport_matches_subscriber
from subscriber.trial import expire_all_trials
from subscriber.sms import send_sms_alert

logger = logging.getLogger(__name__)


class AlertRouter:
    """
    Tier-based deal routing for the freemium subscriber system.

    Routes deals to premium/trial subscribers instantly and queues
    Great deals for the free tier weekly digest. Sends SMS for
    mistake fares to premium subscribers with phone numbers.

    Attributes:
        db: TursoClient instance for database operations.
        manager: SubscriberManager for subscriber queries and trial expiry.
    """

    def __init__(self, db_client=None, manager=None):
        """
        Initialize AlertRouter.

        Args:
            db_client: TursoClient instance. If None, creates a new one.
            manager: SubscriberManager instance. If None, creates one using db_client.
        """
        self.db = db_client or TursoClient()
        self.manager = manager or SubscriberManager(self.db)
        self._subscribers_cache: Optional[list[dict]] = None
        self._email_send_count: int = 0

    def _load_subscribers(self) -> list[dict]:
        """
        Load all active subscribers, caching for the duration of the workflow run.

        On first call, expires all trials (lazy expiry) then loads subscriber list.
        Subsequent calls return the cached list.

        Returns:
            List of active subscriber dicts.
        """
        if self._subscribers_cache is not None:
            return self._subscribers_cache

        # Expire all trials first (lazy, no cron needed)
        expired_count = expire_all_trials(self.manager)
        if expired_count > 0:
            logger.info(f"[ROUTER] Expired {expired_count} trial(s) before routing")

        # Load all active subscribers
        self._subscribers_cache = self.db.get_active_subscribers()
        logger.info(f"[ROUTER] Loaded {len(self._subscribers_cache)} active subscribers")
        return self._subscribers_cache

    def route_deal(self, deal: dict) -> dict:
        """
        Route a single deal to the correct subscribers and delivery channels.

        Routing rules:
          - Premium/trial subscribers get instant emails for ALL deal types
            (Great, WOW, mistake) filtered by metro preferences.
          - Mistake fares also trigger SMS to premium subscribers with phone numbers.
          - Great deals are queued for free tier weekly digest.
          - WOW/mistake deals are queued as FOMO teasers for the digest.

        Args:
            deal: Deal dict with origin, dest, dest_name, price, tier, url,
                  and optionally is_mistake_fare, z_score, observation_count.

        Returns:
            Dict with routing summary:
              {"instant_emails": N, "sms_sent": N, "digest_queued": bool, "skipped_limit": bool}
        """
        subscribers = self._load_subscribers()
        origin = deal.get("origin", "")
        tier = deal.get("tier", "").lower()
        is_mistake = deal.get("is_mistake_fare", False)

        result = {
            "instant_emails": 0,
            "sms_sent": 0,
            "digest_queued": False,
            "skipped_limit": False,
        }

        # Determine deal type for routing
        is_premium_content = tier in ("wow",) or is_mistake
        is_free_content = tier in ("good", "great")

        # --- Premium/Trial instant delivery ---
        # Premium subscribers get instant emails for ALL deal types (SUBS-04)
        if is_premium_content or is_free_content:
            premium_subs = [
                s for s in subscribers
                if s.get("tier") in ("premium", "trial")
                and airport_matches_subscriber(origin, s)
            ]

            # Send instant email to matching premium/trial subscribers
            for sub in premium_subs:
                if self._email_send_count >= 90:
                    # Leave buffer below 100/day Gmail limit (SUBS-05)
                    logger.warning(
                        "[ROUTER] Approaching Gmail 100/day limit, deferring sends"
                    )
                    result["skipped_limit"] = True
                    break

                success = self._send_instant_email(sub, deal)
                if success:
                    result["instant_emails"] += 1
                    self._email_send_count += 1

            # SMS for mistake fares to premium subscribers with phone numbers
            if is_mistake:
                for sub in premium_subs:
                    if sub.get("phone"):
                        if send_sms_alert(sub["phone"], deal):
                            result["sms_sent"] += 1

        # --- Queue for weekly digest ---
        # Great deals -> queued as free content
        if is_free_content:
            self._queue_for_digest(deal, is_teaser=False)
            result["digest_queued"] = True

        # WOW/mistake deals -> queued as FOMO teaser content (FRML-01)
        if is_premium_content:
            self._queue_for_digest(deal, is_teaser=True)
            result["digest_queued"] = True

        logger.info(
            f"[ROUTER] {origin}-{deal.get('dest', '???')} ({tier}): "
            f"emails={result['instant_emails']}, sms={result['sms_sent']}, "
            f"digest={'queued' if result['digest_queued'] else 'skipped'}"
        )
        return result

    def _send_instant_email(self, subscriber: dict, deal: dict) -> bool:
        """
        Send an instant deal alert email to a single subscriber.

        Uses the existing Gmail SMTP pipeline from mvp0_sender.
        Includes historical price context for premium subscribers.

        Args:
            subscriber: Subscriber dict with at least 'email' key.
            deal: Deal dict with deal details.

        Returns:
            True if email sent successfully, False otherwise.
        """
        try:
            from mvp0_sender import send_to_subscriber
        except ImportError:
            logger.error("[ROUTER] mvp0_sender not available for email delivery")
            return False

        email = subscriber.get("email")
        if not email:
            return False

        # Build subject using alert templates
        from alert.templates import format_alert_subject, get_tier_label

        tier = deal.get("tier", "great")
        is_mistake = deal.get("is_mistake_fare", False)
        is_escalation = deal.get("is_escalation", False)
        tier_label, tier_emoji = get_tier_label(tier, is_mistake_fare=is_mistake)
        price_cents = int(deal.get("price", 0) * 100)
        last_price_cents = (
            int(deal["last_alert_price"]) if deal.get("last_alert_price") else None
        )

        subject = format_alert_subject(
            route=f"{deal.get('origin', '???')}-{deal.get('dest', '???')}",
            dest_name=deal.get("dest_name", deal.get("dest", "Unknown")),
            price_cents=price_cents,
            tier=tier_label,
            tier_emoji=tier_emoji,
            is_escalation=is_escalation,
            last_price_cents=last_price_cents,
        )

        # Build HTML body using the existing email template from deal_finder
        from deal_finder import format_destination_card_html, build_email_content

        # For single-deal instant email, wrap in a list to reuse build_email_content
        _, plain_body, html_body = build_email_content([deal])

        # Add historical price context for premium subscribers (SUBS-04)
        observation_count = deal.get("observation_count")
        z_score = deal.get("z_score")
        if observation_count and z_score:
            price_context = (
                f"This price is {abs(z_score):.1f} standard deviations below "
                f"the 90-day average ({observation_count} observations)"
            )
            # Insert context before the footer in plain body
            plain_body = plain_body.replace(
                "\n---",
                f"\n{price_context}\n\n---",
                1,
            )

        try:
            success = send_to_subscriber(email, subject, html_body, plain_body)
            if success:
                logger.info(f"[ROUTER] Instant email sent to {email}")
            else:
                logger.warning(f"[ROUTER] Failed to send instant email to {email}")
            # Match existing delay pattern from mvp0_sender (0.5s between sends)
            time.sleep(0.5)
            return success
        except Exception as e:
            logger.error(f"[ROUTER] Email send error for {email}: {e}")
            return False

    def _queue_for_digest(self, deal: dict, is_teaser: bool = False) -> bool:
        """
        Queue a deal for inclusion in the weekly digest email.

        If is_teaser is True, marks the deal as expired/FOMO content so
        the digest builder can show it differently (e.g., "This WOW deal
        was available to premium subscribers").

        Args:
            deal: Deal dict with origin, dest, dest_name, price, tier.
            is_teaser: If True, marks as FOMO teaser content for free tier.

        Returns:
            True if successfully queued, False otherwise.
        """
        # Build price_cents from price if needed
        if "price_cents" in deal:
            price_cents = deal["price_cents"]
        else:
            price_cents = int(deal.get("price", 0) * 100)

        entry = {
            "route": f"{deal.get('origin', '???')}-{deal.get('dest', '???')}",
            "origin": deal.get("origin", ""),
            "dest": deal.get("dest", ""),
            "dest_name": deal.get("dest_name", ""),
            "price_cents": price_cents,
            "tier": deal.get("tier", "great"),
        }

        # Mark as expired/teaser for FOMO content in free tier digest (FRML-01)
        if is_teaser:
            entry["expired"] = 1

        try:
            success = self.db.queue_deal_for_digest(entry)
            if success:
                logger.debug(
                    f"[ROUTER] Queued for digest: {entry['route']} "
                    f"(teaser={is_teaser})"
                )
            return success
        except Exception as e:
            logger.error(f"[ROUTER] Failed to queue for digest: {e}")
            return False

    def route_deals(self, deals: list[dict]) -> dict:
        """
        Route multiple deals. Returns aggregate summary.

        Args:
            deals: List of deal dicts.

        Returns:
            Aggregate routing summary dict.
        """
        totals = {
            "instant_emails": 0,
            "sms_sent": 0,
            "digest_queued": 0,
            "skipped_limit": False,
        }

        for deal in deals:
            result = self.route_deal(deal)
            totals["instant_emails"] += result["instant_emails"]
            totals["sms_sent"] += result["sms_sent"]
            if result["digest_queued"]:
                totals["digest_queued"] += 1
            if result["skipped_limit"]:
                totals["skipped_limit"] = True

        logger.info(
            f"[ROUTER] Routed {len(deals)} deals: "
            f"{totals['instant_emails']} instant emails, "
            f"{totals['sms_sent']} SMS, "
            f"{totals['digest_queued']} queued for digest"
        )
        return totals
