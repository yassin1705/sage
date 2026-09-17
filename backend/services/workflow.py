from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from backend.agent import QwenAgent
from backend.db import Database
from backend.integrations import GmailSender


CLASS_LABELS = {
    "COLLECTION_STATUS": "Collection status",
    "REPAIR_STATUS": "Repair status",
    "BOOKING_CHANGE": "Booking change",
    "REPEATED_ENQUIRY": "Repeated enquiry",
    "GENERAL_REQUEST": "General request",
}
LABEL_TO_CLASS = {value: key for key, value in CLASS_LABELS.items()}
CHANNEL_LABELS = {
    "SIMULATOR": "Web chat",
    "WEB_CHAT": "Web chat",
    "WHATSAPP": "WhatsApp",
    "GMAIL": "Gmail",
    "VOICE": "Phone note",
    "PHONE_NOTE": "Phone note",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def compact_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def normalize_registration(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


class WorkflowService:
    def __init__(self, database: Database, agent: QwenAgent, gmail: GmailSender) -> None:
        self.database = database
        self.agent = agent
        self.gmail = gmail

    async def create_customer_request(
        self,
        *,
        customer_id: str,
        registration: str,
        delivery_email: str,
        consent: bool,
        message: str,
    ) -> dict[str, object]:
        if not consent:
            raise ValueError("Email delivery consent is required for this demonstration")

        normalized_registration = normalize_registration(registration)
        with self.database.session() as connection:
            identity = connection.execute(
                """
                SELECT c.id AS customer_id, c.preferred_language, c.contact_permission,
                       v.id AS vehicle_id, v.registration_normalized, sj.id AS job_id
                FROM customers c
                JOIN vehicles v ON v.customer_id = c.id
                JOIN service_jobs sj ON sj.vehicle_id = v.id
                WHERE c.id = ? AND v.registration_normalized = ?
                ORDER BY sj.created_at DESC
                LIMIT 1
                """,
                (customer_id.strip().upper(), normalized_registration),
            ).fetchone()
        if identity is None:
            raise LookupError("Customer reference and vehicle registration do not match")

        now = utc_now()
        message_id = compact_id("MSG")
        with self.database.transaction() as connection:
            conversation = connection.execute(
                """
                SELECT id FROM conversations
                WHERE customer_id = ? AND job_id = ? AND state != 'RESOLVED'
                ORDER BY opened_at DESC LIMIT 1
                """,
                (identity["customer_id"], identity["job_id"]),
            ).fetchone()
            conversation_id = conversation["id"] if conversation else compact_id("CASE")
            if conversation is None:
                connection.execute(
                    """
                    INSERT INTO conversations (
                        id, customer_id, job_id, state, delivery_email,
                        email_consent_at, opened_at
                    ) VALUES (?, ?, ?, 'CHECKING_RECORDS', ?, ?, ?)
                    """,
                    (
                        conversation_id,
                        identity["customer_id"],
                        identity["job_id"],
                        delivery_email,
                        now,
                        now,
                    ),
                )
            else:
                connection.execute(
                    """
                    UPDATE conversations
                    SET state = 'CHECKING_RECORDS', delivery_email = ?, email_consent_at = ?
                    WHERE id = ?
                    """,
                    (delivery_email, now, conversation_id),
                )
            connection.execute(
                """
                INSERT INTO messages (
                    id, conversation_id, channel, direction, content,
                    language, delivery_status, created_at
                ) VALUES (?, ?, 'SIMULATOR', 'INBOUND', ?, ?, 'RECEIVED', ?)
                """,
                (message_id, conversation_id, message.strip(), identity["preferred_language"], now),
            )

        analysis = await self.agent.analyze(message.strip(), identity["preferred_language"])
        rule_result = self._evaluate_rules(
            job_id=identity["job_id"],
            intent=analysis.intent,
            agent_response=analysis.proposed_response,
        )

        classification_id = compact_id("CLASS")
        decision_id = compact_id("DEC")
        review_id = compact_id("REVIEW")
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO classifications (
                    id, message_id, intent, confidence, extracted_entities_json,
                    model_name, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    classification_id,
                    message_id,
                    analysis.intent,
                    analysis.confidence,
                    json.dumps({"job_id": identity["job_id"], "registration": normalized_registration}),
                    analysis.model_name,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO decisions (
                    id, message_id, outcome, justification, proposed_response,
                    rules_triggered_json, rule_version, model_name, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'c01-v1', ?, ?)
                """,
                (
                    decision_id,
                    message_id,
                    rule_result["outcome"],
                    rule_result["justification"],
                    rule_result["proposed_response"],
                    json.dumps(rule_result["rules"]),
                    analysis.model_name,
                    now,
                ),
            )
            for evidence in rule_result["evidence"]:
                connection.execute(
                    """
                    INSERT INTO decision_evidence (
                        decision_id, source_type, source_record_id, field_name,
                        captured_value, observed_at
                    ) VALUES (?, 'JOB_STATUS_EVENT', ?, 'status_value', ?, ?)
                    """,
                    (
                        decision_id,
                        f"{identity['job_id']}:{evidence['source']}:{evidence['status_type']}",
                        evidence["status_value"],
                        evidence["observed_at"],
                    ),
                )
            connection.execute(
                """
                INSERT INTO reviews (id, decision_id, status, created_at)
                VALUES (?, ?, 'PENDING', ?)
                """,
                (review_id, decision_id, now),
            )
            connection.execute(
                "UPDATE conversations SET state = 'WAITING_HUMAN_REVIEW' WHERE id = ?",
                (conversation_id,),
            )
            connection.execute(
                """
                INSERT INTO audit_events (
                    entity_type, entity_id, event_type, actor_type, actor_id,
                    details_json, created_at
                ) VALUES ('REVIEW', ?, 'CREATED', 'AGENT', ?, ?, ?)
                """,
                (
                    review_id,
                    analysis.model_name,
                    json.dumps({"intent": analysis.intent, "summary": analysis.summary}),
                    now,
                ),
            )

        return {
            "conversation_id": conversation_id,
            "review_id": review_id,
            "state": "WAITING_HUMAN_REVIEW",
            "message": "Your request is waiting for a service adviser to review the proposed response.",
            "model": analysis.model_name,
        }

    def _evaluate_rules(self, *, job_id: str, intent: str, agent_response: str) -> dict[str, object]:
        with self.database.session() as connection:
            rows = connection.execute(
                """
                SELECT source, status_type, status_value, observed_at
                FROM job_status_events
                WHERE job_id = ?
                ORDER BY observed_at DESC, id DESC
                """,
                (job_id,),
            ).fetchall()
        evidence = [dict(row) for row in rows]
        latest = {(row["source"], row["status_type"]): row["status_value"] for row in rows}

        if intent == "COLLECTION_STATUS":
            quality = latest.get(("QUALITY_CONTROL", "QUALITY_CHECK"))
            crm = latest.get(("CRM", "COLLECTION"))
            if quality != "COMPLETE" or crm == "READY":
                return {
                    "outcome": "NEEDS_REVIEW",
                    "rules": ["CONFLICTING_JOB_STATES", "COLLECTION_REQUIRES_ADVISER"],
                    "justification": (
                        "The workshop reports that work is finished, but the final quality check "
                        "is pending while CRM reports the vehicle as ready. A service adviser must "
                        "resolve the conflict before collection can be promised."
                    ),
                    "proposed_response": (
                        "The workshop has completed the work, but the final quality check is still "
                        "pending. I cannot confirm collection yet. A service adviser will review "
                        "this and contact you."
                    ),
                    "evidence": evidence,
                }

        if intent == "BOOKING_CHANGE":
            return {
                "outcome": "CALLBACK",
                "rules": ["RESPECT_CONTACT_PERMISSION", "NO_AUTOMATIC_BOOKING_CHANGE"],
                "justification": (
                    "The booking exists, but changes require a service adviser. The customer "
                    "record permits callback contact only."
                ),
                "proposed_response": (
                    "I found your current booking. A service adviser will call you to arrange a "
                    "different time. Your booking remains unchanged until then."
                ),
                "evidence": evidence,
            }

        return {
            "outcome": "NEEDS_REVIEW",
            "rules": ["HUMAN_APPROVAL_REQUIRED"],
            "justification": "The agent prepared a response from the available records. A manager must approve it before email delivery.",
            "proposed_response": agent_response or "A service adviser is reviewing your request and will respond shortly.",
            "evidence": evidence,
        }

    def list_manager_inquiries(self) -> list[dict[str, object]]:
        with self.database.session() as connection:
            rows = connection.execute(
                """
                SELECT r.id AS review_id, r.status AS review_status, r.reviewed_at,
                       d.id AS decision_id, d.outcome, d.justification,
                       d.proposed_response, d.rules_triggered_json,
                       m.id AS message_id, m.channel, m.content, m.created_at,
                       cl.intent, cl.confidence,
                       conv.id AS conversation_id, conv.delivery_email,
                       c.id AS customer_id, c.preferred_language,
                       sj.id AS job_id, v.registration_normalized,
                       out.delivery_status, out.created_at AS delivered_at
                FROM reviews r
                JOIN decisions d ON d.id = r.decision_id
                JOIN messages m ON m.id = d.message_id
                JOIN classifications cl ON cl.message_id = m.id
                JOIN conversations conv ON conv.id = m.conversation_id
                JOIN customers c ON c.id = conv.customer_id
                LEFT JOIN service_jobs sj ON sj.id = conv.job_id
                LEFT JOIN vehicles v ON v.id = sj.vehicle_id
                LEFT JOIN messages out ON out.id = (
                    SELECT om.id FROM messages om
                    WHERE om.conversation_id = conv.id AND om.direction = 'OUTBOUND'
                    ORDER BY om.created_at DESC LIMIT 1
                )
                ORDER BY r.created_at DESC
                """
            ).fetchall()

            result: list[dict[str, object]] = []
            for row in rows:
                evidence_rows = connection.execute(
                    """
                    SELECT source_type, source_record_id, captured_value, observed_at
                    FROM decision_evidence WHERE decision_id = ? ORDER BY id
                    """,
                    (row["decision_id"],),
                ).fetchall()
                evidence = []
                for evidence_row in evidence_rows:
                    source_parts = evidence_row["source_record_id"].split(":")
                    source = source_parts[1].replace("_", " ").title() if len(source_parts) > 1 else evidence_row["source_type"].title()
                    value = evidence_row["captured_value"].replace("_", " ").title()
                    tone = "warning" if value.upper() in {"PENDING", "READY"} else "positive" if value.upper() in {"FINISHED", "CONFIRMED", "COMPLETE"} else "neutral"
                    evidence.append({"source": source, "value": value, "observedAt": evidence_row["observed_at"] or "Customer record", "tone": tone})

                review_status = row["review_status"]
                if review_status == "REJECTED":
                    ui_status = "rejected"
                elif review_status in {"APPROVED", "CORRECTED"}:
                    ui_status = "sent"
                elif row["outcome"] == "CALLBACK":
                    ui_status = "ready"
                else:
                    ui_status = "needs_review"
                result.append({
                    "id": row["review_id"],
                    "customerId": row["customer_id"],
                    "customerLanguage": row["preferred_language"],
                    "customerEmail": row["delivery_email"],
                    "channel": CHANNEL_LABELS.get(row["channel"], "Web chat"),
                    "receivedAt": row["created_at"],
                    "message": row["content"],
                    "jobId": row["job_id"] or "No job",
                    "vehicle": f"{row['registration_normalized'] or 'Unknown'} · Service case",
                    "classification": CLASS_LABELS.get(row["intent"], "General request"),
                    "confidence": round(row["confidence"] * 100),
                    "status": ui_status,
                    "justification": row["justification"],
                    "rules": json.loads(row["rules_triggered_json"]),
                    "evidence": evidence,
                    "proposedResponse": row["proposed_response"],
                    "deliveredAt": row["delivered_at"],
                    "deliveryStatus": row["delivery_status"],
                })
        return result

    def get_customer_case(self, conversation_id: str) -> dict[str, object] | None:
        with self.database.session() as connection:
            row = connection.execute(
                """
                SELECT conv.id, conv.state, conv.delivery_email, conv.job_id,
                       r.status AS review_status, r.final_response,
                       out.delivery_status, out.created_at AS delivered_at
                FROM conversations conv
                LEFT JOIN messages inbound ON inbound.id = (
                    SELECT im.id FROM messages im
                    WHERE im.conversation_id = conv.id AND im.direction = 'INBOUND'
                    ORDER BY im.created_at DESC LIMIT 1
                )
                LEFT JOIN decisions d ON d.message_id = inbound.id
                LEFT JOIN reviews r ON r.decision_id = d.id
                LEFT JOIN messages out ON out.id = (
                    SELECT om.id FROM messages om
                    WHERE om.conversation_id = conv.id AND om.direction = 'OUTBOUND'
                    ORDER BY om.created_at DESC LIMIT 1
                )
                WHERE conv.id = ?
                """,
                (conversation_id,),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def approve_review(
        self,
        *,
        review_id: str,
        final_response: str,
        classification_label: str,
        reviewer_id: str = "demo-manager",
    ) -> dict[str, object]:
        now = utc_now()
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT r.status, r.decision_id, d.message_id, d.proposed_response,
                       m.conversation_id, conv.delivery_email, conv.job_id,
                       cl.id AS classification_id
                FROM reviews r
                JOIN decisions d ON d.id = r.decision_id
                JOIN messages m ON m.id = d.message_id
                JOIN classifications cl ON cl.message_id = m.id
                JOIN conversations conv ON conv.id = m.conversation_id
                WHERE r.id = ?
                """,
                (review_id,),
            ).fetchone()
            if row is None:
                raise LookupError("Review not found")
            if not row["delivery_email"]:
                raise ValueError("The customer case has no approved delivery email")
            if row["status"] in {"APPROVED", "CORRECTED"}:
                return {"status": "already_sent", "review_id": review_id}

            corrected = final_response.strip() != row["proposed_response"].strip()
            review_status = "CORRECTED" if corrected else "APPROVED"
            intent = LABEL_TO_CLASS.get(classification_label, "GENERAL_REQUEST")
            connection.execute(
                "UPDATE classifications SET intent = ? WHERE id = ?",
                (intent, row["classification_id"]),
            )
            connection.execute(
                "UPDATE decisions SET proposed_response = ? WHERE id = ?",
                (final_response.strip(), row["decision_id"]),
            )
            connection.execute(
                """
                UPDATE reviews
                SET status = ?, reviewer_id = ?, final_response = ?, reviewed_at = ?
                WHERE id = ?
                """,
                (review_status, reviewer_id, final_response.strip(), now, review_id),
            )
            connection.execute(
                "UPDATE conversations SET state = 'RESPONSE_APPROVED' WHERE id = ?",
                (row["conversation_id"],),
            )
            outbound_id = compact_id("OUT")
            connection.execute(
                """
                INSERT INTO messages (
                    id, conversation_id, channel, direction, content,
                    language, delivery_status, created_at
                ) VALUES (?, ?, 'GMAIL', 'OUTBOUND', ?, 'English', 'DRAFT', ?)
                """,
                (outbound_id, row["conversation_id"], final_response.strip(), now),
            )

        subject = f"Update on your vehicle request — {row['conversation_id']}"
        email_body = (
            f"Hello,\n\n{final_response.strip()}\n\n"
            f"Reference: {row['conversation_id']}\n"
            f"Vehicle case: {row['job_id'] or 'Not assigned'}\n\n"
            "This response was reviewed and approved by a service adviser.\n"
        )
        try:
            delivery = self.gmail.send(row["delivery_email"], subject, email_body)
        except Exception as error:
            with self.database.transaction() as connection:
                connection.execute(
                    "UPDATE messages SET delivery_status = 'FAILED', external_message_id = ? WHERE id = ?",
                    (str(error)[:300], outbound_id),
                )
                connection.execute(
                    """
                    INSERT INTO audit_events (
                        entity_type, entity_id, event_type, actor_type, actor_id,
                        details_json, created_at
                    ) VALUES ('REVIEW', ?, 'DELIVERY_FAILED', 'SYSTEM', NULL, ?, ?)
                    """,
                    (review_id, json.dumps({"error": str(error)}), utc_now()),
                )
            raise RuntimeError(f"Email delivery failed: {error}") from error

        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE messages SET delivery_status = ?, external_message_id = ?
                WHERE id = ?
                """,
                (delivery.status, delivery.provider_message_id, outbound_id),
            )
            connection.execute(
                "UPDATE conversations SET state = 'RESOLVED', resolved_at = ? WHERE id = ?",
                (utc_now(), row["conversation_id"]),
            )
            connection.execute(
                """
                INSERT INTO audit_events (
                    entity_type, entity_id, event_type, actor_type, actor_id,
                    details_json, created_at
                ) VALUES ('REVIEW', ?, 'APPROVED_AND_DELIVERED', 'MANAGER', ?, ?, ?)
                """,
                (
                    review_id,
                    reviewer_id,
                    json.dumps({"delivery_mode": delivery.mode, "status": delivery.status}),
                    utc_now(),
                ),
            )
        return {
            "status": delivery.status,
            "mode": delivery.mode,
            "review_id": review_id,
            "conversation_id": row["conversation_id"],
        }

    def reject_review(self, review_id: str, note: str, reviewer_id: str = "demo-manager") -> None:
        now = utc_now()
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT m.conversation_id
                FROM reviews r
                JOIN decisions d ON d.id = r.decision_id
                JOIN messages m ON m.id = d.message_id
                WHERE r.id = ?
                """,
                (review_id,),
            ).fetchone()
            if row is None:
                raise LookupError("Review not found")
            connection.execute(
                """
                UPDATE reviews SET status = 'REJECTED', reviewer_id = ?,
                    reviewer_note = ?, reviewed_at = ? WHERE id = ?
                """,
                (reviewer_id, note.strip(), now, review_id),
            )
            connection.execute(
                "UPDATE conversations SET state = 'WAITING_HUMAN_REVIEW' WHERE id = ?",
                (row["conversation_id"],),
            )
