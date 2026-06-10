import json
import os
import re as _re
import time

from flask import Blueprint, jsonify, request

from .shared import get_db, login_required

bp = Blueprint('rotina', __name__)


@bp.route("/api/rotina/hoje", methods=["GET"])
@login_required
def rotina_hoje():
    from datetime import date
    today = date.today().isoformat()
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM habits WHERE active = TRUE ORDER BY category, id")
        habits = list(cur.fetchall())
        if not habits:
            return jsonify([])
        ids = [h["id"] for h in habits]
        cur.execute(
            "SELECT habit_id, completed FROM habit_logs WHERE date = %s AND habit_id = ANY(%s)",
            (today, ids)
        )
        logs = {r["habit_id"]: r["completed"] for r in cur.fetchall()}
        cur.execute(
            "SELECT habit_id, current_streak, best_streak FROM streaks WHERE habit_id = ANY(%s)",
            (ids,)
        )
        streaks = {r["habit_id"]: r for r in cur.fetchall()}
        result = []
        for h in habits:
            hid = h["id"]
            result.append({
                "id": hid,
                "name": h["name"],
                "category": h["category"],
                "icon": h["icon"],
                "completed": logs.get(hid, False),
                "current_streak": streaks.get(hid, {}).get("current_streak", 0),
                "best_streak": streaks.get(hid, {}).get("best_streak", 0),
            })
        return jsonify(result)
    finally:
        conn.close()


@bp.route("/api/rotina/check", methods=["POST"])
@login_required
def rotina_check():
    from datetime import date, timedelta
    data = request.get_json()
    habit_id = data.get("habit_id")
    if not habit_id:
        return jsonify({"error": "habit_id required"}), 400
    log_date = data.get("date", date.today().isoformat())
    completed = data.get("completed", True)
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO habit_logs (habit_id, date, completed)
            VALUES (%s, %s, %s)
            ON CONFLICT (habit_id, date) DO UPDATE SET completed = EXCLUDED.completed
        """, (habit_id, log_date, completed))
        cur.execute("""
            SELECT date FROM habit_logs
            WHERE habit_id = %s AND completed = TRUE
            ORDER BY date DESC
        """, (habit_id,))
        rows = [r["date"] for r in cur.fetchall()]
        current_streak = 0
        if rows:
            check = date.today()
            for d in rows:
                if d >= check - timedelta(days=1):
                    current_streak += 1
                    check = d
                else:
                    break
        cur.execute("""
            INSERT INTO streaks (habit_id, current_streak, best_streak, last_updated)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (habit_id) DO UPDATE SET
                current_streak = EXCLUDED.current_streak,
                best_streak = GREATEST(streaks.best_streak, EXCLUDED.current_streak),
                last_updated = EXCLUDED.last_updated
        """, (habit_id, current_streak, current_streak, date.today().isoformat()))
        conn.commit()
        return jsonify({"ok": True, "current_streak": current_streak})
    finally:
        conn.close()


@bp.route("/api/rotina/streaks", methods=["GET"])
@login_required
def rotina_streaks():
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT h.id, h.name, h.icon, h.category,
                   COALESCE(s.current_streak, 0) as current_streak,
                   COALESCE(s.best_streak, 0) as best_streak
            FROM habits h
            LEFT JOIN streaks s ON s.habit_id = h.id
            WHERE h.active = TRUE
            ORDER BY s.current_streak DESC NULLS LAST
        """)
        return jsonify(list(cur.fetchall()))
    finally:
        conn.close()


@bp.route("/api/rotina/semana", methods=["GET"])
@login_required
def rotina_semana():
    from datetime import date, timedelta
    today = date.today()
    days = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT date::text, COUNT(*) FILTER (WHERE completed = TRUE) as done,
                   COUNT(*) as total
            FROM habit_logs
            WHERE date = ANY(%s)
            GROUP BY date ORDER BY date
        """, (days,))
        logs = {r["date"]: {"done": r["done"], "total": r["total"]} for r in cur.fetchall()}
        cur.execute("SELECT COUNT(*) as c FROM habits WHERE active = TRUE")
        total_habits = cur.fetchone()["c"]
        result = []
        for d in days:
            result.append({
                "date": d,
                "done": logs.get(d, {}).get("done", 0),
                "total": total_habits,
            })
        return jsonify(result)
    finally:
        conn.close()


@bp.route("/api/rotina/maconha", methods=["POST"])
@login_required
def rotina_maconha_post():
    from datetime import date
    data = request.get_json()
    log_date = data.get("date", date.today().isoformat())
    period = data.get("period", "noite")
    if period not in ("dia", "noite"):
        return jsonify({"error": "period must be 'dia' or 'noite'"}), 400
    used = data.get("used", True)
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO maconha_log (date, used, period)
            VALUES (%s, %s, %s)
            ON CONFLICT (date, period) DO UPDATE SET used = EXCLUDED.used
        """, (log_date, used, period))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@bp.route("/api/rotina/maconha/mes", methods=["GET"])
@login_required
def rotina_maconha_mes():
    from datetime import date
    today = date.today()
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT date::text, period, used FROM maconha_log
            WHERE EXTRACT(MONTH FROM date) = %s AND EXTRACT(YEAR FROM date) = %s
            ORDER BY date DESC
        """, (today.month, today.year))
        return jsonify(list(cur.fetchall()))
    finally:
        conn.close()

