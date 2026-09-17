from __future__ import annotations

import json
from datetime import datetime, timezone

from .database import Database


EXERCISE_TIME = "2026-09-17T09:00:00+01:00"


def json_value(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def seed_database(database: Database) -> None:
    database.initialize()

    with database.transaction() as connection:
        connection.executemany(
            """
            INSERT INTO customers (id, preferred_language, contact_permission)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                preferred_language = excluded.preferred_language,
                contact_permission = excluded.contact_permission
            """,
            [
                ("CUS-A", "French", "service updates only"),
                ("CUS-B", "English", "callback only"),
            ],
        )

        connection.executemany(
            """
            INSERT INTO vehicles (id, customer_id, registration_normalized, make, model)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                customer_id = excluded.customer_id,
                registration_normalized = excluded.registration_normalized,
                make = excluded.make,
                model = excluded.model
            """,
            [
                ("VEH-1", "CUS-A", "ABC123", "Porsche", "Taycan (synthetic)"),
                ("VEH-2", "CUS-B", "XYZ908", "Porsche", "Macan (synthetic)"),
            ],
        )

        connection.executemany(
            """
            INSERT INTO service_jobs (
                id, vehicle_id, appointment_at, current_stage,
                current_owner_role, version, workflow_updated_at
            ) VALUES (?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(id) DO UPDATE SET
                vehicle_id = excluded.vehicle_id,
                appointment_at = excluded.appointment_at
            """,
            [
                ("JOB-1", "VEH-1", None, "QUALITY_CHECK_PENDING", "QUALITY_CONTROLLER", EXERCISE_TIME),
                ("JOB-2", "VEH-2", "Exercise Day 2, 10:00", "BOOKING_CONFIRMED", "SERVICE_ADVISER", "2026-09-17T09:10:00+01:00"),
            ],
        )
        connection.execute(
            """
            UPDATE service_jobs
            SET current_stage = COALESCE(current_stage, 'QUALITY_CHECK_PENDING'),
                current_owner_role = COALESCE(current_owner_role, 'QUALITY_CONTROLLER'),
                workflow_updated_at = COALESCE(workflow_updated_at, ?)
            WHERE id = 'JOB-1'
            """,
            (EXERCISE_TIME,),
        )
        connection.execute(
            """
            UPDATE service_jobs
            SET current_stage = COALESCE(current_stage, 'BOOKING_CONFIRMED'),
                current_owner_role = COALESCE(current_owner_role, 'SERVICE_ADVISER'),
                workflow_updated_at = COALESCE(workflow_updated_at, ?)
            WHERE id = 'JOB-2'
            """,
            ("2026-09-17T09:10:00+01:00",),
        )

        connection.executemany(
            """
            INSERT INTO workflow_stage_rules (
                current_stage, action, required_role, next_stage, next_owner_role
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(current_stage, action) DO UPDATE SET
                required_role = excluded.required_role,
                next_stage = excluded.next_stage,
                next_owner_role = excluded.next_owner_role
            """,
            [
                ("VEHICLE_RECEIVED", "START_DIAGNOSIS", "RECEPTION", "DIAGNOSIS", "TECHNICIAN"),
                ("DIAGNOSIS", "START_REPAIR", "TECHNICIAN", "REPAIR_IN_PROGRESS", "TECHNICIAN"),
                ("REPAIR_IN_PROGRESS", "FINISH_REPAIR", "TECHNICIAN", "QUALITY_CHECK_PENDING", "QUALITY_CONTROLLER"),
                ("QUALITY_CHECK_PENDING", "COMPLETE_QUALITY_CHECK", "QUALITY_CONTROLLER", "READY_FOR_COLLECTION", "SERVICE_ADVISER"),
                ("READY_FOR_COLLECTION", "CONFIRM_CUSTOMER_NOTIFIED", "SERVICE_ADVISER", "CUSTOMER_NOTIFIED", "SERVICE_ADVISER"),
                ("CUSTOMER_NOTIFIED", "CONFIRM_COLLECTION", "SERVICE_ADVISER", "COLLECTED", "SERVICE_ADVISER"),
            ],
        )

        connection.executemany(
            """
            INSERT INTO workflow_events (
                job_id, previous_stage, new_stage, action, completed_by,
                completed_by_role, previous_owner_role, next_owner_role,
                notes, simulated, created_at
            )
            SELECT ?, NULL, ?, 'INITIALIZE_WORKFLOW', 'seed-system',
                   'SYSTEM', NULL, ?, 'Synthetic exercise starting state', 0, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM workflow_events
                WHERE job_id = ? AND action = 'INITIALIZE_WORKFLOW'
            )
            """,
            [
                ("JOB-1", "QUALITY_CHECK_PENDING", "QUALITY_CONTROLLER", EXERCISE_TIME, "JOB-1"),
                ("JOB-2", "BOOKING_CONFIRMED", "SERVICE_ADVISER", "2026-09-17T09:10:00+01:00", "JOB-2"),
            ],
        )

        status_rows = [
            ("JOB-1", "WORKSHOP", "WORK", "FINISHED", "2026-09-17T09:00:00+01:00"),
            ("JOB-1", "QUALITY_CONTROL", "QUALITY_CHECK", "PENDING", "2026-09-17T09:00:00+01:00"),
            ("JOB-1", "CRM", "COLLECTION", "READY", "2026-09-17T09:00:00+01:00"),
            ("JOB-2", "WORKSHOP", "APPOINTMENT", "BOOKED", "2026-09-17T09:10:00+01:00"),
            ("JOB-2", "CRM", "BOOKING", "CONFIRMED", "2026-09-17T09:10:00+01:00"),
        ]
        connection.executemany(
            """
            INSERT INTO job_status_events (
                job_id, source, status_type, status_value, observed_at, raw_payload_json
            ) VALUES (?, ?, ?, ?, ?, '{}')
            ON CONFLICT(job_id, source, status_type, observed_at) DO UPDATE SET
                status_value = excluded.status_value
            """,
            status_rows,
        )

        connection.executemany(
            """
            INSERT INTO conversations (id, customer_id, job_id, state, opened_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET state = excluded.state
            """,
            [
                ("CONV-1", "CUS-A", "JOB-1", "WAITING_HUMAN_REVIEW", "2026-09-17T09:14:00+01:00"),
                ("CONV-2", "CUS-B", "JOB-2", "WAITING_HUMAN_REVIEW", "2026-09-17T09:32:00+01:00"),
            ],
        )

        connection.executemany(
            """
            INSERT INTO messages (
                id, conversation_id, external_message_id, channel, direction,
                content, language, delivery_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                content = excluded.content,
                delivery_status = excluded.delivery_status
            """,
            [
                ("MSG-1", "CONV-1", None, "SIMULATOR", "INBOUND", "Can I collect my car this afternoon?", "English", "RECEIVED", "2026-09-17T09:14:00+01:00"),
                ("MSG-2", "CONV-1", None, "PHONE_NOTE", "INBOUND", "I asked about collecting the same car. Please call me.", "English", "RECEIVED", "2026-09-17T09:21:00+01:00"),
                ("MSG-3", "CONV-2", None, "WEB_CHAT", "INBOUND", "I need to change my service booking.", "English", "RECEIVED", "2026-09-17T09:32:00+01:00"),
            ],
        )

        connection.executemany(
            """
            INSERT INTO classifications (
                id, message_id, intent, confidence, extracted_entities_json,
                model_name, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                intent = excluded.intent,
                confidence = excluded.confidence,
                extracted_entities_json = excluded.extracted_entities_json
            """,
            [
                ("CLASS-1", "MSG-1", "COLLECTION_STATUS", 0.96, json_value({"job_id": "JOB-1"}), "seeded-demonstration", "2026-09-17T09:14:02+01:00"),
                ("CLASS-2", "MSG-2", "REPEATED_ENQUIRY", 0.91, json_value({"job_id": "JOB-1", "related_message_id": "MSG-1"}), "seeded-demonstration", "2026-09-17T09:21:02+01:00"),
                ("CLASS-3", "MSG-3", "BOOKING_CHANGE", 0.98, json_value({"job_id": "JOB-2"}), "seeded-demonstration", "2026-09-17T09:32:02+01:00"),
            ],
        )

        decisions = [
            (
                "DEC-1", "MSG-1", "NEEDS_REVIEW",
                "Workshop work is finished, but quality control is pending while CRM reports ready for collection.",
                "The workshop has completed the work, but the final quality check is still pending. I cannot confirm collection yet. A service adviser will review this and contact you.",
                json_value(["CONFLICTING_JOB_STATES", "COLLECTION_REQUIRES_ADVISER"]),
            ),
            (
                "DEC-2", "MSG-2", "NEEDS_REVIEW",
                "The message concerns the same unresolved vehicle and collection request as MSG-1.",
                "I found your earlier request about the same vehicle. Collection is not yet confirmed because the quality check is pending. A service adviser is reviewing the case.",
                json_value(["GROUP_RELATED_ENQUIRIES", "COLLECTION_REQUIRES_ADVISER"]),
            ),
            (
                "DEC-3", "MSG-3", "CALLBACK",
                "The booking is confirmed and the customer's contact permission allows callbacks only.",
                "I found your booking for Day 2 at 10:00. A service adviser will call you to arrange a different time. Your current booking remains unchanged until then.",
                json_value(["RESPECT_CONTACT_PERMISSION", "NO_SIMULATED_BOOKING_CONFIRMATION"]),
            ),
        ]
        connection.executemany(
            """
            INSERT INTO decisions (
                id, message_id, outcome, justification, proposed_response,
                rules_triggered_json, rule_version, model_name, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'c01-v1', 'seeded-demonstration', ?)
            ON CONFLICT(id) DO UPDATE SET
                outcome = excluded.outcome,
                justification = excluded.justification,
                proposed_response = excluded.proposed_response,
                rules_triggered_json = excluded.rules_triggered_json
            """,
            [(*decision, "2026-09-17T09:14:04+01:00") for decision in decisions],
        )

        evidence_rows = [
            ("DEC-1", "WORKFLOW_STATE", "JOB-1:AUTHORITATIVE_WORKFLOW:CURRENT_STAGE", "current_stage", "QUALITY_CHECK_PENDING", "2026-09-17T09:00:00+01:00"),
            ("DEC-1", "JOB_STATUS_EVENT", "JOB-1:WORKSHOP:WORK", "status_value", "FINISHED", "2026-09-17T09:00:00+01:00"),
            ("DEC-1", "JOB_STATUS_EVENT", "JOB-1:QUALITY_CONTROL:QUALITY_CHECK", "status_value", "PENDING", "2026-09-17T09:00:00+01:00"),
            ("DEC-1", "JOB_STATUS_EVENT", "JOB-1:CRM:COLLECTION", "status_value", "READY", "2026-09-17T09:00:00+01:00"),
            ("DEC-2", "MESSAGE", "MSG-1", "content", "Can I collect my car this afternoon?", "2026-09-17T09:14:00+01:00"),
            ("DEC-2", "CUSTOMER", "CUS-A", "contact_permission", "service updates only", None),
            ("DEC-3", "SERVICE_JOB", "JOB-2", "appointment_at", "Exercise Day 2, 10:00", "2026-09-17T09:10:00+01:00"),
            ("DEC-3", "CUSTOMER", "CUS-B", "contact_permission", "callback only", None),
        ]
        connection.executemany(
            """
            INSERT INTO decision_evidence (
                decision_id, source_type, source_record_id, field_name,
                captured_value, observed_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(decision_id, source_type, source_record_id, field_name)
            DO UPDATE SET
                captured_value = excluded.captured_value,
                observed_at = excluded.observed_at
            """,
            evidence_rows,
        )

        connection.executemany(
            """
            INSERT INTO reviews (id, decision_id, status, created_at)
            VALUES (?, ?, 'PENDING', ?)
            ON CONFLICT(id) DO NOTHING
            """,
            [
                ("REVIEW-1", "DEC-1", "2026-09-17T09:14:05+01:00"),
                ("REVIEW-2", "DEC-2", "2026-09-17T09:21:05+01:00"),
                ("REVIEW-3", "DEC-3", "2026-09-17T09:32:05+01:00"),
            ],
        )

        connection.executemany(
            """
            INSERT INTO channel_connections (
                id, channel, status, account_label, configuration_json, updated_at
            ) VALUES (?, ?, ?, NULL, '{}', ?)
            ON CONFLICT(id) DO UPDATE SET status = excluded.status
            """,
            [
                ("CONN-WHATSAPP", "WHATSAPP", "NOT_CONNECTED", EXERCISE_TIME),
                ("CONN-GMAIL", "GMAIL", "NOT_CONNECTED", EXERCISE_TIME),
                ("CONN-VOICE", "VOICE", "PLANNED", EXERCISE_TIME),
            ],
        )

        connection.execute(
            """
            INSERT INTO audit_events (
                entity_type, entity_id, event_type, actor_type, details_json, created_at
            )
            SELECT 'DATABASE', 'C01', 'SYNTHETIC_SEED_APPLIED', 'SYSTEM', ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM audit_events
                WHERE entity_type = 'DATABASE'
                  AND entity_id = 'C01'
                  AND event_type = 'SYNTHETIC_SEED_APPLIED'
            )
            """,
            (
                json_value({"data_status": "SYNTHETIC EXERCISE DATA"}),
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def main() -> None:
    database = Database()
    seed_database(database)
    print(f"Seeded synthetic C01 database: {database.path}")
    print(f"Tables: {', '.join(database.table_names())}")


if __name__ == "__main__":
    main()
