#!/usr/bin/env python3
"""HTML dashboard generator — standalone HTML report with inline CSS/JS."""

import json
import sqlite3
from datetime import UTC, datetime

from scripts.metrics import (
    compute_cycle_times,
    compute_progress,
    compute_velocity,
    detect_stalls,
    forecast_completion,
)
from scripts.retro import compute_failure_rate, compute_shipping_streak


def generate_dashboard_data(conn: sqlite3.Connection, project_id: str = "default") -> dict:
    """Collect all dashboard data from the database."""
    from scripts.state import get_status, compute_next_action

    progress = compute_progress(conn, project_id)
    velocity = compute_velocity(conn, project_id)
    cycle_times = compute_cycle_times(conn, project_id)
    stalls = detect_stalls(conn, project_id)
    forecast = forecast_completion(conn, project_id)
    streak = compute_shipping_streak(conn, project_id)
    failures = compute_failure_rate(conn, project_id)
    status = get_status(conn)
    next_action = compute_next_action(conn)

    # Get recent learnings count
    learnings_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM learning WHERE project_id = ?",
        (project_id,),
    ).fetchone()["cnt"]

    # Get total decisions
    decisions_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM decision WHERE project_id = ?",
        (project_id,),
    ).fetchone()["cnt"]

    # Workstream portfolio panel
    from scripts.workstreams import get_all_workstreams_progress, get_active_workstream
    workstreams = get_all_workstreams_progress(conn, project_id)
    active_workstream = get_active_workstream(conn, project_id)

    return {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "project": status.get("project", {}),
        "milestone": progress.get("milestone"),
        "phases": progress.get("phases", []),
        "velocity": velocity,
        "cycle_times": cycle_times,
        "stalls": stalls,
        "forecast": forecast,
        "streak": streak,
        "failures": failures,
        "next_action": next_action,
        "learnings_count": learnings_count,
        "decisions_count": decisions_count,
        "workstreams": workstreams,
        "active_workstream": active_workstream,
    }


def render_html(data: dict) -> str:
    """Render dashboard data as a standalone HTML page with inline CSS."""
    project_name = data.get("project", {}).get("name", "Meridian Project")
    milestone = data.get("milestone") or {}
    milestone_name = milestone.get("name", "No milestone")
    milestone_pct = milestone.get("pct", 0)
    phases = data.get("phases", [])
    vel = data.get("velocity", {})
    ct = data.get("cycle_times", {})
    forecast = data.get("forecast", {})
    stalls = data.get("stalls", [])
    failures = data.get("failures", {})

    # Determine health
    stall_count = len(stalls)
    if stall_count == 0 and vel.get("velocity", 0) > 0:
        health = "ON TRACK"
        health_color = "#22c55e"
    elif stall_count <= 2:
        health = "AT RISK"
        health_color = "#f59e0b"
    else:
        health = "STALLED"
        health_color = "#ef4444"

    # Build phase rows
    # Build workstream rows
    workstreams = data.get("workstreams", [])
    active_ws = data.get("active_workstream")
    active_ws_slug = active_ws["slug"] if active_ws else None
    ws_rows = ""
    for entry in workstreams:
        ws = entry["workstream"]
        marker = " ★" if ws["slug"] == active_ws_slug else ""
        ws_status_colors = {
            "active": "#22c55e", "paused": "#f59e0b",
            "complete": "#94a3b8", "archived": "#475569",
        }
        wcolor = ws_status_colors.get(ws["status"], "#6b7280")
        ms_count = len(entry["milestones"])
        pct = entry["overall_pct"]
        ws_rows += f"""
        <tr>
            <td><b>{ws['name']}{marker}</b><br><small style="color:#94a3b8">{ws['slug']}</small></td>
            <td><span style="color:{wcolor};font-weight:600">{ws['status']}</span></td>
            <td>{ms_count}</td>
            <td>{entry['complete_phases']}/{entry['total_phases']}</td>
            <td>
                <div style="background:#e5e7eb;border-radius:4px;height:8px;width:80px;display:inline-block;vertical-align:middle">
                    <div style="background:{wcolor};border-radius:4px;height:8px;width:{min(pct, 100) * 0.8:.0f}px"></div>
                </div>
                {pct}%
            </td>
        </tr>"""

    phase_rows = ""
    for p in phases:
        status_colors = {
            "complete": "#22c55e", "executing": "#3b82f6", "planned": "#6b7280",
            "blocked": "#ef4444", "reviewing": "#8b5cf6", "verifying": "#06b6d4",
            "context_gathered": "#f59e0b", "planned_out": "#f59e0b",
        }
        color = status_colors.get(p["status"], "#6b7280")
        phase_rows += f"""
        <tr>
            <td>{p.get('id', '')}</td>
            <td>{p['name']}</td>
            <td><span style="color:{color};font-weight:600">{p['status']}</span></td>
            <td>{p['done']}/{p['total']}</td>
            <td>
                <div style="background:#e5e7eb;border-radius:4px;height:8px;width:100px;display:inline-block">
                    <div style="background:{color};border-radius:4px;height:8px;width:{p['pct']}px"></div>
                </div>
                {p['pct']}%
            </td>
        </tr>"""

    # Build stall rows
    stall_rows = ""
    if stalls:
        for s in stalls:
            stall_rows += f"<li>{s['entity_type'].title()}: <b>{s['name']}</b> — stuck {s['stuck_hours']}h in {s['status']}</li>"
    else:
        stall_rows = "<li>None</li>"

    next_action = data.get("next_action", {})
    next_action_text = next_action.get("action", "No action") if isinstance(next_action, dict) else str(next_action)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Meridian Dashboard — {project_name}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; padding: 24px; }}
  .container {{ max-width: 960px; margin: 0 auto; }}
  h1 {{ font-size: 24px; margin-bottom: 4px; }}
  .subtitle {{ color: #94a3b8; font-size: 14px; margin-bottom: 24px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }}
  .card {{ background: #1e293b; border-radius: 8px; padding: 16px; }}
  .card-label {{ color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }}
  .card-value {{ font-size: 28px; font-weight: 700; }}
  .card-detail {{ color: #94a3b8; font-size: 13px; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ text-align: left; color: #94a3b8; font-size: 12px; text-transform: uppercase; padding: 8px; border-bottom: 1px solid #334155; }}
  td {{ padding: 8px; border-bottom: 1px solid #1e293b; }}
  .section {{ background: #1e293b; border-radius: 8px; padding: 20px; margin-bottom: 16px; }}
  .section h2 {{ font-size: 16px; margin-bottom: 12px; }}
  .health {{ display: inline-block; padding: 4px 12px; border-radius: 4px; font-weight: 700; font-size: 14px; }}
  .next-action {{ background: #1e3a5f; border-left: 4px solid #3b82f6; padding: 12px 16px; border-radius: 0 8px 8px 0; margin-top: 16px; }}
  ul {{ list-style: none; }}
  li {{ padding: 4px 0; }}
  li::before {{ content: "→ "; color: #94a3b8; }}
</style>
</head>
<body>
<div class="container">
  <h1>Meridian Dashboard — {project_name}</h1>
  <p class="subtitle">Generated {data['generated_at']}</p>

  <div class="grid">
    <div class="card">
      <div class="card-label">Health</div>
      <div class="card-value"><span class="health" style="background:{health_color}20;color:{health_color}">{health}</span></div>
    </div>
    <div class="card">
      <div class="card-label">Milestone</div>
      <div class="card-value">{milestone_pct}%</div>
      <div class="card-detail">{milestone_name}</div>
    </div>
    <div class="card">
      <div class="card-label">Velocity</div>
      <div class="card-value">{vel.get('velocity', 0)}</div>
      <div class="card-detail">plans/day ({vel.get('window_days', 7)}d avg)</div>
    </div>
    <div class="card">
      <div class="card-label">Shipping Streak</div>
      <div class="card-value">{data['streak']}</div>
      <div class="card-detail">consecutive phases</div>
    </div>
    <div class="card">
      <div class="card-label">Cycle Time</div>
      <div class="card-value">{ct.get('plan_avg_hours', '—')}</div>
      <div class="card-detail">hrs/plan avg</div>
    </div>
    <div class="card">
      <div class="card-label">Failure Rate</div>
      <div class="card-value">{failures.get('rate', 0)}%</div>
      <div class="card-detail">{failures.get('failed', 0)}/{failures.get('total', 0)} plans</div>
    </div>
    <div class="card">
      <div class="card-label">ETA</div>
      <div class="card-value">{forecast.get('eta_date', '—')}</div>
      <div class="card-detail">{forecast.get('remaining_plans', 0)} plans remaining</div>
    </div>
    <div class="card">
      <div class="card-label">Knowledge</div>
      <div class="card-value">{data['learnings_count']}</div>
      <div class="card-detail">learnings / {data['decisions_count']} decisions</div>
    </div>
  </div>

  <div class="section">
    <h2>Phases</h2>
    <table>
      <thead><tr><th>#</th><th>Phase</th><th>Status</th><th>Plans</th><th>Progress</th></tr></thead>
      <tbody>{phase_rows if phase_rows else '<tr><td colspan="5">No phases yet</td></tr>'}</tbody>
    </table>
  </div>

  <div class="section">
    <h2>Stalls</h2>
    <ul>{stall_rows}</ul>
  </div>

  {'<div class="section"><h2>Workstreams ★ = active session track</h2><table><thead><tr><th>Workstream</th><th>Status</th><th>Milestones</th><th>Phases Done</th><th>Progress</th></tr></thead><tbody>' + ws_rows + '</tbody></table></div>' if workstreams else ''}

  <div class="next-action">
    <strong>Next Action:</strong> {next_action_text}
  </div>
</div>
</body>
</html>"""


def write_dashboard(conn: sqlite3.Connection, output_path: str, project_id: str = "default") -> str:
    """Generate and write HTML dashboard to a file.

    Returns the output path.
    """
    data = generate_dashboard_data(conn, project_id)
    html = render_html(data)
    with open(output_path, "w") as f:
        f.write(html)
    return output_path
