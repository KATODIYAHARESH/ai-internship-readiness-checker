"""Plotly figure factories used by the tabs."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .. import config as cfg
from ..models import ScoreResult
from .components import LEVEL_COLORS

GREEN, AMBER, RED, BLUE, GREY = "#16a34a", "#d97706", "#dc2626", "#2563eb", "rgba(148,163,184,0.30)"


def _color(fraction: float) -> str:
    return GREEN if fraction >= 0.75 else AMBER if fraction >= 0.5 else RED


def _base(fig: go.Figure, height: int, title: str | None = None) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=40 if title else 10, b=10),
        title=dict(text=title, x=0.01, font=dict(size=15)) if title else None,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def score_gauge(score: float, level: str) -> go.Figure:
    """Semi-circular gauge with the three readiness bands."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"font": {"size": 46}, "valueformat": ".1f"},
            title={"text": level, "font": {"size": 18, "color": LEVEL_COLORS.get(level, BLUE)}},
            gauge={
                "axis": {"range": [0, 100], "tickvals": [0, 50, 75, 100]},
                "bar": {"color": LEVEL_COLORS.get(level, BLUE), "thickness": 0.32},
                "steps": [
                    {"range": [0, cfg.ALMOST_THRESHOLD], "color": "rgba(220,38,38,0.16)"},
                    {"range": [cfg.ALMOST_THRESHOLD, cfg.READY_THRESHOLD], "color": "rgba(217,119,6,0.16)"},
                    {"range": [cfg.READY_THRESHOLD, 100], "color": "rgba(22,163,74,0.16)"},
                ],
            },
        )
    )
    return _base(fig, 250)


def breakdown_chart(result: ScoreResult) -> go.Figure:
    """Horizontal bars: points earned versus the maximum for every component."""
    comps = list(result.components)
    names = [c.name for c in comps]
    fig = go.Figure()
    fig.add_bar(y=names, x=[c.weight for c in comps], orientation="h", marker_color=GREY, name="Max points", hoverinfo="skip")
    fig.add_bar(
        y=names,
        x=[c.points for c in comps],
        orientation="h",
        marker_color=[_color(c.fraction) for c in comps],
        text=[f"{c.points:.1f} / {c.weight:.0f}" for c in comps],
        textposition="inside",
        insidetextanchor="start",
        name="Earned",
        customdata=[c.detail for c in comps],
        hovertemplate="%{y}: %{x:.1f} pts<br>%{customdata}<extra></extra>",
    )
    fig.update_layout(barmode="overlay", showlegend=False, xaxis_title="Points", yaxis=dict(autorange="reversed"))
    return _base(fig, 290, "Score breakdown (weighted)")


def role_fit_chart(role_scores: dict[str, float], selected: str) -> go.Figure:
    """Bars comparing the same profile across all target roles."""
    items = sorted(role_scores.items(), key=lambda kv: kv[1])
    fig = go.Figure(
        go.Bar(
            x=[v for _, v in items],
            y=[k for k, _ in items],
            orientation="h",
            marker_color=[BLUE if k == selected else "rgba(100,116,139,0.55)" for k, _ in items],
            text=[f"{v:.1f}" for _, v in items],
            textposition="outside",
        )
    )
    fig.update_layout(xaxis=dict(range=[0, 105], title="Readiness score"))
    return _base(fig, 240, "Readiness by role")


def level_donut(dist: pd.DataFrame) -> go.Figure:
    """Donut chart of students per readiness level."""
    fig = go.Figure(
        go.Pie(
            labels=dist["level"],
            values=dist["students"],
            hole=0.58,
            marker_colors=[LEVEL_COLORS[lv] for lv in dist["level"]],
            sort=False,
            textinfo="value+percent",
        )
    )
    fig.update_layout(legend=dict(orientation="h", y=-0.05))
    return _base(fig, 320, "Readiness levels")


def department_chart(depts: pd.DataFrame) -> go.Figure:
    """Average score per department, with the Ready/Almost thresholds marked."""
    data = depts.sort_values("avg_score")
    fig = go.Figure(
        go.Bar(
            x=data["avg_score"],
            y=data["major"],
            orientation="h",
            marker_color=[
                GREEN if v >= cfg.READY_THRESHOLD else AMBER if v >= cfg.ALMOST_THRESHOLD else RED
                for v in data["avg_score"]
            ],
            text=[f"{v:.1f}  ({r:.0f}% ready)" for v, r in zip(data["avg_score"], data["pct_ready"])],
            textposition="auto",
        )
    )
    fig.add_vline(x=cfg.ALMOST_THRESHOLD, line_dash="dot", line_color=AMBER)
    fig.add_vline(x=cfg.READY_THRESHOLD, line_dash="dot", line_color=GREEN)
    fig.update_layout(xaxis=dict(range=[0, 100], title="Average readiness score"))
    return _base(fig, 320, "Readiness by department")


def skill_gap_chart(gaps: pd.DataFrame) -> go.Figure:
    """Most common missing required skills."""
    data = gaps.sort_values("pct_students")
    fig = go.Figure(
        go.Bar(
            x=data["pct_students"],
            y=data["skill"],
            orientation="h",
            marker_color=RED,
            text=[f"{p:.0f}% ({n})" for p, n in zip(data["pct_students"], data["students_missing"])],
            textposition="auto",
        )
    )
    fig.update_layout(xaxis_title="% of students missing the skill")
    return _base(fig, 340, "Top campus-wide skill gaps")


def component_chart(comp: pd.DataFrame) -> go.Figure:
    """Average points per component compared with the maximum."""
    fig = go.Figure()
    fig.add_bar(x=comp["component"], y=comp["max_points"], marker_color=GREY, name="Max")
    fig.add_bar(
        x=comp["component"],
        y=comp["avg_points"],
        marker_color=BLUE,
        name="Campus average",
        text=[f"{v:.1f}" for v in comp["avg_points"]],
        textposition="outside",
    )
    fig.update_layout(barmode="overlay", legend=dict(orientation="h", y=1.12))
    return _base(fig, 340, "Average points per component")


def score_scatter(scored: pd.DataFrame) -> go.Figure:
    """CGPA versus readiness score, coloured by level."""
    fig = go.Figure()
    for level, color in LEVEL_COLORS.items():
        sub = scored[scored["level"] == level]
        if sub.empty:
            continue
        fig.add_scatter(
            x=sub["cgpa"],
            y=sub["score"],
            mode="markers",
            name=level,
            marker=dict(color=color, size=9, opacity=0.85),
            text=sub["name"],
            hovertemplate="%{text}<br>CGPA %{x:.2f}<br>Score %{y:.1f}<extra></extra>",
        )
    fig.update_layout(xaxis_title="CGPA", yaxis_title="Readiness score", legend=dict(orientation="h", y=1.12))
    return _base(fig, 340, "CGPA is not the whole story")
