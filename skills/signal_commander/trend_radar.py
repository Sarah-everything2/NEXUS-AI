"""NEXUS SIGNAL COMMANDER - Evidence-aware opportunity scoring."""

import math
from datetime import datetime


def score_signal(signal):
    views = max(0, int(signal.get("views", 0) or 0))
    likes_raw = signal.get("likes")
    likes = max(0, int(likes_raw or 0)) if likes_raw is not None else None

    components = {}
    weights = {}

    # Audience demand: logarithmic scale, based on observed views.
    if views > 0:
        components["audience_demand"] = min(
            100, math.log10(views + 1) / 6 * 100
        )
        weights["audience_demand"] = 0.60

    # Engagement is only scored when actual likes and views exist.
    if likes is not None and views > 0:
        engagement_rate = likes / views * 100
        components["engagement"] = min(100, engagement_rate * 10)
        weights["engagement"] = 0.25
    else:
        engagement_rate = None

    # Recency is scored only when the upload date was measured.
    age_status = signal.get("age_data_status")
    age_hours = signal.get("age_hours")

    if age_status == "MEASURED" and age_hours is not None:
        age_hours = max(0, float(age_hours))
        components["recency"] = max(
            0, 100 - (age_hours / 168 * 100)
        )
        weights["recency"] = 0.15

    total_weight = sum(weights.values())

    score = (
        sum(components[key] * weights[key] for key in components)
        / total_weight
        if total_weight else 0
    )

    # Missing competition data must never be presented as measured.
    competition_measured = (
        signal.get("competition_status") == "MEASURED"
        and signal.get("competition") is not None
    )

    # Views alone cannot prove that a video is currently trending.
    trend_status = "INSUFFICIENT_TREND_DATA"

    if (
        age_status == "MEASURED"
        and signal.get("view_velocity") is not None
    ):
        trend_status = "MOMENTUM_DATA_AVAILABLE"

    if len(components) >= 3:
        confidence = "HIGH"
    elif len(components) == 2:
        confidence = "MEDIUM"
    elif len(components) == 1:
        confidence = "LOW"
    else:
        confidence = "INSUFFICIENT_DATA"

    return {
        "score": round(score, 2),
        "score_type": "EVIDENCE_AWARE_DISCOVERY_SCORE",
        "audience_demand_score": round(
            components.get("audience_demand", 0), 2
        ),
        "engagement_score": round(
            components.get("engagement", 0), 2
        ),
        "engagement_rate": (
            round(engagement_rate, 2)
            if engagement_rate is not None else None
        ),
        "recency_score": round(
            components.get("recency", 0), 2
        ),
        "competition": (
            signal.get("competition")
            if competition_measured else None
        ),
        "competition_status": (
            "MEASURED" if competition_measured else "UNMEASURED"
        ),
        "trend_status": trend_status,
        "confidence": confidence,
        "available_evidence": list(components.keys()),
        "missing_evidence": [
            field for field, available in {
                "views": views > 0,
                "likes": likes is not None,
                "upload_date": age_status == "MEASURED",
                "competition": competition_measured,
                "view_velocity": signal.get("view_velocity") is not None,
            }.items() if not available
        ],
        "scored_at": datetime.now().isoformat(),
    }


def rank_signals(signals):
    ranked = []

    for signal in signals:
        item = dict(signal)
        item["radar"] = score_signal(item)
        ranked.append(item)

    return sorted(
        ranked,
        key=lambda item: item["radar"]["score"],
        reverse=True
    )
