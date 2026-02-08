"""Automation rule model for advanced automation rules engine."""

from datetime import datetime
from typing import Optional, List, Dict

from sqlalchemy import String, Integer, Float, DateTime, Boolean, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AutomationRule(Base):
    """User-defined automation rule with conditions and actions."""

    __tablename__ = "automation_rules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Rule identity
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Owner (multi-user)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True)

    # Trigger type determines when the rule is evaluated
    trigger: Mapped[str] = mapped_column(String(50), index=True)
    # Triggers: new_release, library_sync, recommendation_generated,
    #           listening_milestone, new_artist_discovered, schedule

    # Schedule (for schedule trigger)
    schedule_cron: Mapped[Optional[str]] = mapped_column(String(100))

    # Conditions - all must be true for rule to fire (AND logic)
    conditions: Mapped[List[Dict]] = mapped_column(JSON, default=list)
    # Each condition: {"field": "genre", "operator": "contains", "value": "rock"}
    # Fields: genre, artist_name, album_type, release_year, confidence_score,
    #         audio_energy, audio_danceability, audio_valence, popularity,
    #         seeders, format, quality, play_count, source
    # Operators: equals, not_equals, contains, not_contains, greater_than,
    #            less_than, in_list, not_in_list, matches_regex

    # Actions - executed in order when conditions match
    actions: Mapped[List[Dict]] = mapped_column(JSON, default=list)
    # Each action: {"type": "add_to_wishlist", "params": {"priority": "high", "auto_download": true}}
    # Action types: add_to_wishlist, start_download, add_to_playlist, send_notification,
    #               tag_item, set_quality_profile, skip_item, add_to_library

    # Execution tracking
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    trigger_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text)

    # Priority (higher = evaluated first)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<AutomationRule(id={self.id}, name={self.name}, trigger={self.trigger})>"


class AutomationLog(Base):
    """Log of automation rule executions."""

    __tablename__ = "automation_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    rule_id: Mapped[int] = mapped_column(ForeignKey("automation_rules.id"), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))

    # What triggered it
    trigger_type: Mapped[str] = mapped_column(String(50))
    trigger_data: Mapped[Optional[Dict]] = mapped_column(JSON, default=dict)

    # Result
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    actions_executed: Mapped[List[Dict]] = mapped_column(JSON, default=list)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Context
    matched_items: Mapped[Optional[List[Dict]]] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<AutomationLog(id={self.id}, rule_id={self.rule_id}, success={self.success})>"
