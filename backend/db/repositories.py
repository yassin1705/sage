from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from .database import Database


@dataclass(frozen=True)
class ReviewCase:
    review_id: str
    review_status: str
    conversation_id: str
    customer_id: str
    preferred_language: str
    contact_permission: str
    job_id: str | None
    vehicle_registration: str | None
    message_id: str
    channel: str
    message: str
    received_at: str
    classification: str
    confidence: float
    outcome: str
    justification: str
    proposed_response: str
    rules_triggered: list[str]


class CaseRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list_review_cases(self, status: str | None = None) -> list[ReviewCase]:
        query = """
            SELECT
                r.id AS review_id,
                r.status AS review_status,
                conv.id AS conversation_id,
                c.id AS customer_id,
                c.preferred_language,
                c.contact_permission,
                conv.job_id,
                v.registration_normalized AS vehicle_registration,
                m.id AS message_id,
                m.channel,
                m.content AS message,
                m.created_at AS received_at,
                cl.intent AS classification,
                cl.confidence,
                d.outcome,
                d.justification,
                d.proposed_response,
                d.rules_triggered_json
            FROM reviews r
            JOIN decisions d ON d.id = r.decision_id
            JOIN messages m ON m.id = d.message_id
            JOIN classifications cl ON cl.message_id = m.id
            JOIN conversations conv ON conv.id = m.conversation_id
            JOIN customers c ON c.id = conv.customer_id
            LEFT JOIN service_jobs sj ON sj.id = conv.job_id
            LEFT JOIN vehicles v ON v.id = sj.vehicle_id
        """
        parameters: tuple[str, ...] = ()
        if status:
            query += " WHERE r.status = ?"
            parameters = (status,)
        query += " ORDER BY r.created_at DESC"

        with self.database.session() as connection:
            rows = connection.execute(query, parameters).fetchall()

        return [self._review_case_from_row(row) for row in rows]

    def get_review_case(self, review_id: str) -> ReviewCase | None:
        cases = self.list_review_cases()
        return next((case for case in cases if case.review_id == review_id), None)

    def evidence_for_decision(self, decision_id: str) -> list[dict[str, str | None]]:
        with self.database.session() as connection:
            rows = connection.execute(
                """
                SELECT source_type, source_record_id, field_name, captured_value, observed_at
                FROM decision_evidence
                WHERE decision_id = ?
                ORDER BY id
                """,
                (decision_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _review_case_from_row(row: sqlite3.Row) -> ReviewCase:
        return ReviewCase(
            review_id=row["review_id"],
            review_status=row["review_status"],
            conversation_id=row["conversation_id"],
            customer_id=row["customer_id"],
            preferred_language=row["preferred_language"],
            contact_permission=row["contact_permission"],
            job_id=row["job_id"],
            vehicle_registration=row["vehicle_registration"],
            message_id=row["message_id"],
            channel=row["channel"],
            message=row["message"],
            received_at=row["received_at"],
            classification=row["classification"],
            confidence=row["confidence"],
            outcome=row["outcome"],
            justification=row["justification"],
            proposed_response=row["proposed_response"],
            rules_triggered=json.loads(row["rules_triggered_json"]),
        )
