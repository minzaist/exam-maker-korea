from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class User:
    id: int
    name: str
    masked_service_number: str
    is_admin: bool


def normalize_service_number(value: str) -> str:
    compact = "".join(ch for ch in value.strip() if ch.isdigit())
    if len(compact) < 8 or len(compact) > 12:
        raise ValueError("군번 형식을 확인해주세요.")
    return compact


def normalize_name(value: str) -> str:
    name = " ".join(value.strip().split())
    if len(name) < 2 or len(name) > 30:
        raise ValueError("이름은 2~30자로 입력해주세요.")
    return name


def mask_service_number(value: str) -> str:
    normalized = normalize_service_number(value)
    return f"{normalized[:2]}-****{normalized[-4:]}"


class Storage:
    backend_name = "로컬 SQLite"

    def __init__(
        self,
        path: str | Path,
        pepper: str,
        admin_service_number: str = "",
        admin_name: str = "",
    ):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.pepper = pepper.encode("utf-8")
        self.admin_service_number = admin_service_number.strip()
        self.admin_name = admin_name.strip()
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _fingerprint(self, service_number: str, name: str) -> str:
        normalized = f"{normalize_service_number(service_number)}\0{normalize_name(name)}"
        return hmac.new(self.pepper, normalized.encode("utf-8"), hashlib.sha256).hexdigest()

    def _initialize(self) -> None:
        with self._lock, self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fingerprint TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    masked_service_number TEXT NOT NULL,
                    is_admin INTEGER NOT NULL DEFAULT 0,
                    consented_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    created_at TEXT NOT NULL,
                    file_names TEXT NOT NULL,
                    exam_types TEXT NOT NULL,
                    question_count INTEGER NOT NULL,
                    title_hint TEXT NOT NULL,
                    additional_notes TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_title TEXT NOT NULL DEFAULT '',
                    error_message TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_activities_created_at ON activities(created_at DESC);
                """
            )
        if self.admin_service_number and self.admin_name:
            self._ensure_admin()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _row_to_user(row: sqlite3.Row) -> User:
        return User(
            id=int(row["id"]),
            name=str(row["name"]),
            masked_service_number=str(row["masked_service_number"]),
            is_admin=bool(row["is_admin"]),
        )

    def _ensure_admin(self) -> None:
        fingerprint = self._fingerprint(self.admin_service_number, self.admin_name)
        now = self._now()
        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT INTO users (fingerprint, name, masked_service_number, is_admin, consented_at, created_at)
                VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT(fingerprint) DO UPDATE SET is_admin=1, name=excluded.name
                """,
                (
                    fingerprint,
                    normalize_name(self.admin_name),
                    mask_service_number(self.admin_service_number),
                    now,
                    now,
                ),
            )

    def signup(self, service_number: str, name: str, consented: bool) -> User:
        if not consented:
            raise ValueError("개인정보 및 이용 기록 안내에 동의해주세요.")
        clean_name = normalize_name(name)
        fingerprint = self._fingerprint(service_number, clean_name)
        now = self._now()
        with self._lock, self._connect() as db:
            try:
                cursor = db.execute(
                    """
                    INSERT INTO users (fingerprint, name, masked_service_number, is_admin, consented_at, created_at)
                    VALUES (?, ?, ?, 0, ?, ?)
                    """,
                    (fingerprint, clean_name, mask_service_number(service_number), now, now),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("이미 가입된 계정입니다. 로그인해주세요.") from exc
            row = db.execute("SELECT * FROM users WHERE id=?", (cursor.lastrowid,)).fetchone()
        return self._row_to_user(row)

    def login(self, service_number: str, name: str) -> User | None:
        fingerprint = self._fingerprint(service_number, name)
        with self._lock, self._connect() as db:
            row = db.execute("SELECT * FROM users WHERE fingerprint=?", (fingerprint,)).fetchone()
        return self._row_to_user(row) if row else None

    def start_activity(
        self,
        user_id: int,
        file_names: list[str],
        exam_types: list[str],
        question_count: int,
        title_hint: str,
        additional_notes: str,
    ) -> int:
        with self._lock, self._connect() as db:
            cursor = db.execute(
                """
                INSERT INTO activities (
                    user_id, created_at, file_names, exam_types, question_count,
                    title_hint, additional_notes, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '진행 중')
                """,
                (
                    user_id,
                    self._now(),
                    json.dumps(file_names, ensure_ascii=False),
                    json.dumps(exam_types, ensure_ascii=False),
                    question_count,
                    title_hint[:200],
                    additional_notes[:2000],
                ),
            )
            return int(cursor.lastrowid)

    def finish_activity(self, activity_id: int, result_title: str) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                "UPDATE activities SET status='완료', result_title=? WHERE id=?",
                (result_title[:300], activity_id),
            )

    def fail_activity(self, activity_id: int, error_message: str) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                "UPDATE activities SET status='실패', error_message=? WHERE id=?",
                (error_message[:1000], activity_id),
            )

    def list_activities(self, limit: int = 300) -> list[dict[str, Any]]:
        with self._lock, self._connect() as db:
            rows = db.execute(
                """
                SELECT a.*, u.name, u.masked_service_number
                FROM activities a JOIN users u ON u.id=a.user_id
                ORDER BY a.id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            for key in ("file_names", "exam_types"):
                try:
                    item[key] = json.loads(item[key])
                except (TypeError, json.JSONDecodeError):
                    item[key] = []
            result.append(item)
        return result

    def stats(self) -> dict[str, int]:
        with self._lock, self._connect() as db:
            users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            total = db.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
            completed = db.execute("SELECT COUNT(*) FROM activities WHERE status='완료'").fetchone()[0]
        return {"users": int(users), "total": int(total), "completed": int(completed)}

    def generation_count_today(self, user_id: int) -> int:
        today_prefix = datetime.now(timezone.utc).date().isoformat()
        with self._lock, self._connect() as db:
            count = db.execute(
                "SELECT COUNT(*) FROM activities WHERE user_id=? AND created_at LIKE ?",
                (user_id, f"{today_prefix}%"),
            ).fetchone()[0]
        return int(count)


class SupabaseStorage:
    """Supabase Data API-backed storage for multi-device deployments."""

    backend_name = "Supabase 영구 DB"

    def __init__(
        self,
        url: str,
        secret_key: str,
        pepper: str,
        admin_service_number: str = "",
        admin_name: str = "",
    ):
        if not url.strip() or not secret_key.strip():
            raise ValueError("Supabase URL과 Secret Key를 모두 설정해주세요.")
        try:
            from supabase import create_client
        except ImportError as exc:  # pragma: no cover - deployment configuration guard
            raise RuntimeError("Supabase 패키지가 설치되지 않았습니다.") from exc

        self.client = create_client(url.strip(), secret_key.strip())
        self.pepper = pepper.encode("utf-8")
        self.admin_service_number = admin_service_number.strip()
        self.admin_name = admin_name.strip()
        self._lock = threading.RLock()
        if self.admin_service_number and self.admin_name:
            self._ensure_admin()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _fingerprint(self, service_number: str, name: str) -> str:
        normalized = f"{normalize_service_number(service_number)}\0{normalize_name(name)}"
        return hmac.new(self.pepper, normalized.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def _row_to_user(row: dict[str, Any]) -> User:
        return User(
            id=int(row["id"]),
            name=str(row["name"]),
            masked_service_number=str(row["masked_service_number"]),
            is_admin=bool(row["is_admin"]),
        )

    def _find_by_fingerprint(self, fingerprint: str) -> dict[str, Any] | None:
        try:
            response = (
                self.client.table("users")
                .select("id,name,masked_service_number,is_admin")
                .eq("fingerprint", fingerprint)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise RuntimeError("계정 DB에 연결하지 못했습니다. 잠시 후 다시 시도해주세요.") from exc
        rows = response.data or []
        return dict(rows[0]) if rows else None

    def _ensure_admin(self) -> None:
        clean_name = normalize_name(self.admin_name)
        fingerprint = self._fingerprint(self.admin_service_number, clean_name)
        existing = self._find_by_fingerprint(fingerprint)
        payload = {
            "fingerprint": fingerprint,
            "name": clean_name,
            "masked_service_number": mask_service_number(self.admin_service_number),
            "is_admin": True,
            "consented_at": self._now(),
            "created_at": self._now(),
        }
        try:
            with self._lock:
                if existing:
                    (
                        self.client.table("users")
                        .update(
                            {
                                "name": clean_name,
                                "masked_service_number": payload["masked_service_number"],
                                "is_admin": True,
                            }
                        )
                        .eq("fingerprint", fingerprint)
                        .execute()
                    )
                else:
                    self.client.table("users").insert(payload).execute()
        except Exception as exc:
            raise RuntimeError(
                "Supabase 연결에 실패했습니다. supabase_schema.sql 실행 여부와 Secrets를 확인해주세요."
            ) from exc

    def signup(self, service_number: str, name: str, consented: bool) -> User:
        if not consented:
            raise ValueError("개인정보 및 이용 기록 안내에 동의해주세요.")
        clean_name = normalize_name(name)
        fingerprint = self._fingerprint(service_number, clean_name)
        if self._find_by_fingerprint(fingerprint):
            raise ValueError("이미 가입된 계정입니다. 로그인해주세요.")
        now = self._now()
        payload = {
            "fingerprint": fingerprint,
            "name": clean_name,
            "masked_service_number": mask_service_number(service_number),
            "is_admin": False,
            "consented_at": now,
            "created_at": now,
        }
        try:
            with self._lock:
                response = self.client.table("users").insert(payload).execute()
        except Exception as exc:
            if self._find_by_fingerprint(fingerprint):
                raise ValueError("이미 가입된 계정입니다. 로그인해주세요.") from exc
            raise RuntimeError("계정을 저장하지 못했습니다. 잠시 후 다시 시도해주세요.") from exc
        rows = response.data or []
        if not rows:
            row = self._find_by_fingerprint(fingerprint)
        else:
            row = dict(rows[0])
        if not row:
            raise RuntimeError("가입 결과를 확인하지 못했습니다.")
        return self._row_to_user(row)

    def login(self, service_number: str, name: str) -> User | None:
        row = self._find_by_fingerprint(self._fingerprint(service_number, name))
        return self._row_to_user(row) if row else None

    def start_activity(
        self,
        user_id: int,
        file_names: list[str],
        exam_types: list[str],
        question_count: int,
        title_hint: str,
        additional_notes: str,
    ) -> int:
        payload = {
            "user_id": user_id,
            "created_at": self._now(),
            "file_names": file_names,
            "exam_types": exam_types,
            "question_count": question_count,
            "title_hint": title_hint[:200],
            "additional_notes": additional_notes[:2000],
            "status": "진행 중",
        }
        response = self.client.table("activities").insert(payload).execute()
        rows = response.data or []
        if not rows:
            raise RuntimeError("생성 기록을 저장하지 못했습니다.")
        return int(rows[0]["id"])

    def finish_activity(self, activity_id: int, result_title: str) -> None:
        (
            self.client.table("activities")
            .update({"status": "완료", "result_title": result_title[:300]})
            .eq("id", activity_id)
            .execute()
        )

    def fail_activity(self, activity_id: int, error_message: str) -> None:
        (
            self.client.table("activities")
            .update({"status": "실패", "error_message": error_message[:1000]})
            .eq("id", activity_id)
            .execute()
        )

    def list_activities(self, limit: int = 300) -> list[dict[str, Any]]:
        response = (
            self.client.table("activities")
            .select("*,users(name,masked_service_number)")
            .order("id", desc=True)
            .limit(limit)
            .execute()
        )
        result: list[dict[str, Any]] = []
        for raw in response.data or []:
            item = dict(raw)
            account = item.pop("users", {}) or {}
            item["name"] = account.get("name", "")
            item["masked_service_number"] = account.get("masked_service_number", "")
            for key in ("file_names", "exam_types"):
                if not isinstance(item.get(key), list):
                    item[key] = []
            result.append(item)
        return result

    def _count(self, table: str, *, status: str | None = None) -> int:
        query = self.client.table(table).select("id", count="exact")
        if status is not None:
            query = query.eq("status", status)
        response = query.limit(1).execute()
        return int(response.count or 0)

    def stats(self) -> dict[str, int]:
        return {
            "users": self._count("users"),
            "total": self._count("activities"),
            "completed": self._count("activities", status="완료"),
        }

    def generation_count_today(self, user_id: int) -> int:
        today = datetime.now(timezone.utc).date()
        start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        response = (
            self.client.table("activities")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .gte("created_at", start.isoformat())
            .lt("created_at", end.isoformat())
            .limit(1)
            .execute()
        )
        return int(response.count or 0)
