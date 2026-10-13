"""
backend/db/database.py — SQLite database connection and table schema manager.
"""
from __future__ import annotations
import os
import sqlite3
import json
from contextlib import contextmanager
from typing import Generator

DB_PATH = os.path.abspath(
    os.environ.get("TWINHEALTH_DB_PATH") or os.path.join(os.path.dirname(__file__), "..", "..", "twinhealth.db")
)


def get_db_connection() -> sqlite3.Connection:
    """Creates a configured connection to the SQLite database with WAL mode and foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH, timeout=20.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite database transactions."""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initializes tables and indexes if they do not exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER,
            sex TEXT,
            demographics_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS assessments (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
            inputs_json TEXT NOT NULL,
            normalized_inputs_json TEXT,
            disease_results_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            provider TEXT NOT NULL DEFAULT 'local',
            data_completeness REAL DEFAULT 0.0,
            warnings_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS clinical_reviews (
            id TEXT PRIMARY KEY,
            assessment_id TEXT NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
            doctor_name TEXT NOT NULL DEFAULT 'Dr. Sarah Mitchell, MD',
            status TEXT NOT NULL DEFAULT 'pending',
            doctor_notes TEXT DEFAULT '',
            requested_tests_json TEXT,
            reviewed_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS care_plans (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
            assessment_id TEXT REFERENCES assessments(id) ON DELETE SET NULL,
            version INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'draft',
            diet_json TEXT NOT NULL,
            exercise_json TEXT NOT NULL,
            lifestyle_json TEXT,
            medications_json TEXT,
            schedule_json TEXT NOT NULL,
            doctor_comments TEXT DEFAULT '',
            approved_by TEXT,
            approved_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS daily_progress (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
            care_plan_id TEXT NOT NULL REFERENCES care_plans(id) ON DELETE CASCADE,
            calendar_date TEXT NOT NULL,
            task_id TEXT NOT NULL,
            category TEXT NOT NULL,
            label TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT,
            notes TEXT DEFAULT '',
            self_reported_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(patient_id, care_plan_id, calendar_date, task_id)
        );

        CREATE INDEX IF NOT EXISTS idx_assessments_patient ON assessments(patient_id);
        CREATE INDEX IF NOT EXISTS idx_assessments_status ON assessments(status);
        CREATE INDEX IF NOT EXISTS idx_reviews_assessment ON clinical_reviews(assessment_id);
        CREATE INDEX IF NOT EXISTS idx_reviews_status ON clinical_reviews(status);
        CREATE INDEX IF NOT EXISTS idx_care_plans_patient ON care_plans(patient_id);
        CREATE INDEX IF NOT EXISTS idx_care_plans_status ON care_plans(status);
        CREATE INDEX IF NOT EXISTS idx_daily_progress_lookup ON daily_progress(patient_id, calendar_date);
        """)
