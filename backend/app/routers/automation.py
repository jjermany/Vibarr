"""Automation rules router for managing and executing user-defined rules."""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.automation_rule import AutomationRule, AutomationLog
from app.services.auth import get_current_user, require_user
from app.models.user import User
from app.services.automation_engine import (
    evaluate_all_conditions,
    build_context_from_item,
    execute_rule_actions,
)

router = APIRouter()


# Request/Response models

class RuleCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    trigger: str
    schedule_cron: Optional[str] = None
    conditions: List[dict] = []
    actions: List[dict] = []
    priority: int = 0
    is_enabled: bool = True


class RuleUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger: Optional[str] = None
    schedule_cron: Optional[str] = None
    conditions: Optional[List[dict]] = None
    actions: Optional[List[dict]] = None
    priority: Optional[int] = None
    is_enabled: Optional[bool] = None


class RuleTestRequest(BaseModel):
    """Test a rule against a sample item."""
    item: dict
    item_type: str = "album"


VALID_TRIGGERS = [
    "new_release", "library_sync", "recommendation_generated",
    "listening_milestone", "new_artist_discovered", "schedule",
]

VALID_OPERATORS = [
    "equals", "not_equals", "contains", "not_contains",
    "greater_than", "less_than", "in_list", "not_in_list", "matches_regex",
]

VALID_ACTION_TYPES = [
    "add_to_wishlist", "start_download", "add_to_playlist",
    "send_notification", "tag_item", "set_quality_profile",
    "skip_item", "add_to_library",
]


def _rule_to_dict(rule: AutomationRule) -> dict:
    """Convert rule to response dict."""
    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "is_enabled": rule.is_enabled,
        "trigger": rule.trigger,
        "schedule_cron": rule.schedule_cron,
        "conditions": rule.conditions or [],
        "actions": rule.actions or [],
        "priority": rule.priority,
        "last_triggered_at": rule.last_triggered_at.isoformat() if rule.last_triggered_at else None,
        "trigger_count": rule.trigger_count,
        "last_error": rule.last_error,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


@router.get("/")
async def list_rules(
    trigger: Optional[str] = None,
    enabled_only: bool = False,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all automation rules."""
    query = select(AutomationRule)

    if current_user:
        query = query.where(
            (AutomationRule.user_id == current_user.id) | (AutomationRule.user_id.is_(None))
        )

    if trigger:
        query = query.where(AutomationRule.trigger == trigger)
    if enabled_only:
        query = query.where(AutomationRule.is_enabled == True)

    result = await db.execute(query.order_by(AutomationRule.priority.desc(), AutomationRule.created_at))
    rules = result.scalars().all()

    return [_rule_to_dict(r) for r in rules]


@router.post("/")
async def create_rule(
    request: RuleCreateRequest,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new automation rule."""
    # Validate trigger
    if request.trigger not in VALID_TRIGGERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid trigger. Must be one of: {', '.join(VALID_TRIGGERS)}",
        )

    # Validate conditions
    for cond in request.conditions:
        op = cond.get("operator", "")
        if op not in VALID_OPERATORS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid operator '{op}'. Must be one of: {', '.join(VALID_OPERATORS)}",
            )

    # Validate actions
    for action in request.actions:
        action_type = action.get("type", "")
        if action_type not in VALID_ACTION_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action type '{action_type}'. Must be one of: {', '.join(VALID_ACTION_TYPES)}",
            )

    rule = AutomationRule(
        name=request.name,
        description=request.description,
        trigger=request.trigger,
        schedule_cron=request.schedule_cron,
        conditions=request.conditions,
        actions=request.actions,
        priority=request.priority,
        is_enabled=request.is_enabled,
        user_id=current_user.id if current_user else None,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    return _rule_to_dict(rule)


@router.get("/triggers")
async def list_triggers():
    """List available triggers, operators, and action types."""
    return {
        "triggers": [
            {"value": "new_release", "label": "New Release", "description": "Fires when a new release is detected from a library artist"},
            {"value": "library_sync", "label": "Library Sync", "description": "Fires after a Plex library sync completes"},
            {"value": "recommendation_generated", "label": "Recommendation Generated", "description": "Fires when new recommendations are generated"},
            {"value": "listening_milestone", "label": "Listening Milestone", "description": "Fires when a play count milestone is reached"},
            {"value": "new_artist_discovered", "label": "New Artist Discovered", "description": "Fires when a new artist is added to the library"},
            {"value": "schedule", "label": "Scheduled", "description": "Fires on a cron schedule"},
        ],
        "operators": [
            {"value": "equals", "label": "Equals"},
            {"value": "not_equals", "label": "Does Not Equal"},
            {"value": "contains", "label": "Contains"},
            {"value": "not_contains", "label": "Does Not Contain"},
            {"value": "greater_than", "label": "Greater Than"},
            {"value": "less_than", "label": "Less Than"},
            {"value": "in_list", "label": "In List"},
            {"value": "not_in_list", "label": "Not In List"},
            {"value": "matches_regex", "label": "Matches Regex"},
        ],
        "action_types": [
            {"value": "add_to_wishlist", "label": "Add to Wishlist", "params": ["priority", "auto_download"]},
            {"value": "start_download", "label": "Start Download", "params": ["format"]},
            {"value": "add_to_playlist", "label": "Add to Playlist", "params": ["playlist_id", "note"]},
            {"value": "send_notification", "label": "Send Notification", "params": ["message"]},
            {"value": "tag_item", "label": "Tag Item", "params": ["tags"]},
            {"value": "set_quality_profile", "label": "Set Quality Profile", "params": ["profile_name"]},
            {"value": "skip_item", "label": "Skip Item", "params": []},
            {"value": "add_to_library", "label": "Add to Library", "params": []},
        ],
        "condition_fields": [
            "genre", "artist_name", "album_type", "album_title", "release_year",
            "confidence_score", "audio_energy", "audio_danceability", "audio_valence",
            "audio_tempo", "audio_acousticness", "audio_instrumentalness",
            "popularity", "seeders", "format", "quality", "play_count",
            "source", "category", "recommendation_type",
        ],
    }


@router.get("/{rule_id}")
async def get_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific automation rule."""
    result = await db.execute(select(AutomationRule).where(AutomationRule.id == rule_id))
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    return _rule_to_dict(rule)


@router.patch("/{rule_id}")
async def update_rule(
    rule_id: int,
    request: RuleUpdateRequest,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an automation rule."""
    result = await db.execute(select(AutomationRule).where(AutomationRule.id == rule_id))
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if current_user and rule.user_id and rule.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this rule")

    update_data = request.model_dump(exclude_unset=True)

    if "trigger" in update_data and update_data["trigger"] not in VALID_TRIGGERS:
        raise HTTPException(status_code=400, detail="Invalid trigger")

    for field, value in update_data.items():
        setattr(rule, field, value)

    await db.commit()
    await db.refresh(rule)
    return _rule_to_dict(rule)


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an automation rule."""
    result = await db.execute(select(AutomationRule).where(AutomationRule.id == rule_id))
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if current_user and rule.user_id and rule.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    await db.delete(rule)
    await db.commit()
    return {"status": "deleted"}


@router.post("/{rule_id}/test")
async def test_rule(
    rule_id: int,
    request: RuleTestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Test a rule against a sample item without executing actions."""
    result = await db.execute(select(AutomationRule).where(AutomationRule.id == rule_id))
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    context = build_context_from_item(request.item, request.item_type)
    conditions_met = evaluate_all_conditions(rule.conditions or [], context)

    return {
        "rule_id": rule.id,
        "rule_name": rule.name,
        "conditions_met": conditions_met,
        "context_evaluated": context,
        "conditions": rule.conditions,
        "actions_that_would_execute": rule.actions if conditions_met else [],
    }


@router.post("/{rule_id}/toggle")
async def toggle_rule(
    rule_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle a rule's enabled state."""
    result = await db.execute(select(AutomationRule).where(AutomationRule.id == rule_id))
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule.is_enabled = not rule.is_enabled
    await db.commit()

    return {"id": rule.id, "is_enabled": rule.is_enabled}


@router.get("/{rule_id}/logs")
async def get_rule_logs(
    rule_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get execution logs for a rule."""
    result = await db.execute(
        select(AutomationLog)
        .where(AutomationLog.rule_id == rule_id)
        .order_by(AutomationLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()

    return [
        {
            "id": log.id,
            "rule_id": log.rule_id,
            "trigger_type": log.trigger_type,
            "success": log.success,
            "actions_executed": log.actions_executed,
            "error_message": log.error_message,
            "matched_items": log.matched_items,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


@router.get("/stats/summary")
async def get_automation_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get automation statistics."""
    total_rules = await db.execute(select(func.count(AutomationRule.id)))
    active_rules = await db.execute(
        select(func.count(AutomationRule.id)).where(AutomationRule.is_enabled == True)
    )
    total_executions = await db.execute(select(func.count(AutomationLog.id)))
    successful = await db.execute(
        select(func.count(AutomationLog.id)).where(AutomationLog.success == True)
    )
    failed = await db.execute(
        select(func.count(AutomationLog.id)).where(AutomationLog.success == False)
    )

    return {
        "total_rules": total_rules.scalar() or 0,
        "active_rules": active_rules.scalar() or 0,
        "total_executions": total_executions.scalar() or 0,
        "successful_executions": successful.scalar() or 0,
        "failed_executions": failed.scalar() or 0,
    }
