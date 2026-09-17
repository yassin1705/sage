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
        language: str,
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
                (message_id, conversation_id, message.strip(), language, now),
            )

        analysis = await self.agent.analyze(message.strip(), language)
        intent = self._normalize_intent(message, analysis.intent)
        rule_result = self._evaluate_rules(
            job_id=identity["job_id"],
            intent=intent,
            agent_response=analysis.proposed_response,
            language=language,
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
                    intent,
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
                is_workflow_state = evidence["source"] == "AUTHORITATIVE_WORKFLOW"
                connection.execute(
                    """
                    INSERT INTO decision_evidence (
                        decision_id, source_type, source_record_id, field_name,
                        captured_value, observed_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        decision_id,
                        "WORKFLOW_STATE" if is_workflow_state else "JOB_STATUS_EVENT",
                        f"{identity['job_id']}:{evidence['source']}:{evidence['status_type']}",
                        "current_stage" if is_workflow_state else "status_value",
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
                    json.dumps({"intent": intent, "summary": analysis.summary}),
                    now,
                ),
            )

        return {
            "conversation_id": conversation_id,
            "review_id": review_id,
            "state": "WAITING_HUMAN_REVIEW",
            "message": rule_result["proposed_response"],
            "model": analysis.model_name,
        }

    @staticmethod
    def _normalize_intent(message: str, model_intent: str) -> str:
        normalized = message.casefold()
        if any(term in normalized for term in ("collect", "collection", "pick up", "pickup", "get my car")):
            return "COLLECTION_STATUS"
        if any(term in normalized for term in ("booking", "appointment", "rendez-vous")):
            return "BOOKING_CHANGE"
        if any(term in normalized for term in ("repair", "réparation", "reparation")):
            return "REPAIR_STATUS"
        return model_intent

    def _evaluate_rules(self, *, job_id: str, intent: str, agent_response: str, language: str) -> dict[str, object]:
        with self.database.session() as connection:
            workflow = connection.execute(
                """
                SELECT current_stage, current_owner_role, workflow_updated_at
                FROM service_jobs WHERE id = ?
                """,
                (job_id,),
            ).fetchone()
            rows = connection.execute(
                """
                SELECT source, status_type, status_value, observed_at
                FROM job_status_events
                WHERE job_id = ?
                ORDER BY observed_at DESC, id DESC
                """,
                (job_id,),
            ).fetchall()
        latest_rows: dict[tuple[str, str], dict[str, object]] = {}
        for row in rows:
            key = (row["source"], row["status_type"])
            if key not in latest_rows:
                latest_rows[key] = dict(row)
        evidence = list(latest_rows.values())
        current_stage = workflow["current_stage"] if workflow else None
        if workflow and current_stage:
            evidence.insert(0, {
                "source": "AUTHORITATIVE_WORKFLOW",
                "status_type": "CURRENT_STAGE",
                "status_value": current_stage,
                "observed_at": workflow["workflow_updated_at"],
            })
        latest = {key: row["status_value"] for key, row in latest_rows.items()}
        french = language.casefold() in {"french", "français", "francais", "fr"}

        if intent == "COLLECTION_STATUS":
            work = latest.get(("WORKSHOP", "WORK"))
            quality = latest.get(("QUALITY_CONTROL", "QUALITY_CHECK"))
            crm = latest.get(("CRM", "COLLECTION"))
            if (
                current_stage == "READY_FOR_COLLECTION"
                and work == "FINISHED"
                and quality == "COMPLETE"
                and crm == "READY"
            ):
                return {
                    "outcome": "ANSWER",
                    "rules": ["STATUS_EVIDENCE_ALIGNED", "COLLECTION_REQUIRES_ADVISER"],
                    "justification": (
                        "The authoritative workflow is now Ready for collection and agrees with "
                        "workshop, quality-control, and CRM evidence. The service adviser retains "
                        "the final collection decision."
                    ),
                    "proposed_response": (
                        "Les travaux et le contrôle qualité final sont terminés, et notre système "
                        "indique que votre véhicule est prêt. Un conseiller doit encore confirmer "
                        "la remise. Après son approbation, nous vous contacterons par e-mail."
                        if french else
                        "The repair work and final quality check are complete, and our system now "
                        "shows your vehicle as ready. A service adviser must still provide the "
                        "final collection confirmation. Once approved, we will contact you by email."
                    ),
                    "evidence": evidence,
                }
            if current_stage != "READY_FOR_COLLECTION" or quality != "COMPLETE":
                return {
                    "outcome": "NEEDS_REVIEW",
                    "rules": ["CONFLICTING_JOB_STATES", "COLLECTION_REQUIRES_ADVISER"],
                    "justification": (
                        "The authoritative workflow assigns the vehicle to quality control, while "
                        "CRM reports it as ready. The controlled workflow prevents a collection "
                        "promise until the quality controller completes the assigned stage."
                    ),
                    "proposed_response": (
                        "Bonne nouvelle : l’atelier a terminé les travaux sur votre véhicule. "
                        "Notre système l’indique comme prêt, mais le contrôle qualité final est "
                        "encore en attente. Dès sa confirmation, nous vous contacterons par e-mail."
                        if french else
                        "Good news — the workshop has finished the work on your car. Our system "
                        "shows it as ready, but the final quality check is still pending, so I "
                        "cannot confirm collection just yet. Once we receive final confirmation, "
                        "we will contact you by email."
                    ),
                    "evidence": evidence,
                }

        if intent == "REPAIR_STATUS":
            work = latest.get(("WORKSHOP", "WORK"))
            quality = latest.get(("QUALITY_CONTROL", "QUALITY_CHECK"))
            if current_stage == "READY_FOR_COLLECTION" and quality == "COMPLETE":
                return {
                    "outcome": "ANSWER",
                    "rules": ["CONTROLLED_WORKFLOW_COMPLETE", "HUMAN_APPROVAL_REQUIRED"],
                    "justification": (
                        "The authoritative workflow records that quality control is complete and "
                        "assigns the next action to the service adviser."
                    ),
                    "proposed_response": (
                        "La réparation et le contrôle qualité sont terminés. Un conseiller doit "
                        "encore confirmer la remise du véhicule. Après son approbation, nous vous "
                        "contacterons par e-mail."
                        if french else
                        "The repair and final quality check are complete. A service adviser must "
                        "still confirm collection. Once approved, we will contact you by email."
                    ),
                    "evidence": evidence,
                }
            if work == "FINISHED" and current_stage == "QUALITY_CHECK_PENDING":
                response = (
                    "La réparation de votre véhicule est terminée. Le contrôle qualité final est "
                    "encore en attente, donc la remise du véhicule n’est pas encore confirmée. "
                    "Un conseiller examine le dossier et nous vous contacterons par e-mail dès "
                    "que le contrôle sera validé."
                    if french else
                    "The repair work on your car is finished. The final quality check is still "
                    "pending, so collection is not confirmed yet. A service adviser is reviewing "
                    "the case, and we will contact you by email as soon as the check is approved."
                )
                return {
                    "outcome": "NEEDS_REVIEW",
                    "rules": ["REPAIR_FINISHED", "QUALITY_CHECK_PENDING", "HUMAN_APPROVAL_REQUIRED"],
                    "justification": (
                        "Workshop data shows the repair is finished, but the final quality check "
                        "has not been completed. The manager retains the final decision."
                    ),
                    "proposed_response": response,
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
            "proposed_response": agent_response or (
                "I found your request and checked the available service records. A service "
                "adviser is reviewing the final answer, and we will contact you by email once "
                "it is confirmed."
            ),
            "evidence": evidence,
        }

    def complete_quality_check_transition(
        self,
        review_id: str,
        actor_id: str = "demo-quality-controller",
        actor_role: str = "QUALITY_CONTROLLER",
    ) -> dict[str, object]:
        with self.database.session() as connection:
            row = connection.execute(
                """
                SELECT r.status AS review_status, r.decision_id,
                       d.model_name, cl.intent, m.language,
                       conv.job_id, sj.current_stage, sj.current_owner_role,
                       sj.version
                FROM reviews r
                JOIN decisions d ON d.id = r.decision_id
                JOIN messages m ON m.id = d.message_id
                JOIN classifications cl ON cl.message_id = m.id
                JOIN conversations conv ON conv.id = m.conversation_id
                JOIN service_jobs sj ON sj.id = conv.job_id
                WHERE r.id = ?
                """,
                (review_id,),
            ).fetchone()
        if row is None:
            raise LookupError("Review not found")
        if row["review_status"] != "PENDING":
            raise ValueError("Only a pending review can receive a workflow transition")
        if row["intent"] not in {"COLLECTION_STATUS", "REPAIR_STATUS"}:
            raise ValueError("This workflow action only applies to a vehicle status inquiry")

        now = utc_now()
        with self.database.transaction() as connection:
            transition = connection.execute(
                """
                SELECT required_role, next_stage, next_owner_role
                FROM workflow_stage_rules
                WHERE current_stage = ? AND action = 'COMPLETE_QUALITY_CHECK'
                """,
                (row["current_stage"],),
            ).fetchone()
            if transition is None:
                raise ValueError(f"No quality-control transition is allowed from {row['current_stage']}")
            if transition["required_role"] != actor_role or row["current_owner_role"] != actor_role:
                raise ValueError("Only the quality controller assigned to this stage can complete it")
            updated = connection.execute(
                """
                UPDATE service_jobs
                SET current_stage = ?, current_owner_role = ?,
                    version = version + 1, workflow_updated_at = ?
                WHERE id = ? AND current_stage = ?
                  AND current_owner_role = ? AND version = ?
                """,
                (
                    transition["next_stage"],
                    transition["next_owner_role"],
                    now,
                    row["job_id"],
                    row["current_stage"],
                    row["current_owner_role"],
                    row["version"],
                ),
            )
            if updated.rowcount != 1:
                raise ValueError("The job changed while this action was being applied; refresh and retry")
            connection.execute(
                """
                INSERT INTO workflow_events (
                    job_id, previous_stage, new_stage, action, completed_by,
                    completed_by_role, previous_owner_role, next_owner_role,
                    notes, simulated, created_at
                ) VALUES (?, ?, ?, 'COMPLETE_QUALITY_CHECK', ?, ?, ?, ?,
                          'Synthetic role-authorized workflow transition', 1, ?)
                """,
                (
                    row["job_id"],
                    row["current_stage"],
                    transition["next_stage"],
                    actor_id,
                    actor_role,
                    row["current_owner_role"],
                    transition["next_owner_role"],
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO job_status_events (
                    job_id, source, status_type, status_value,
                    observed_at, raw_payload_json
                ) VALUES (?, 'QUALITY_CONTROL', 'QUALITY_CHECK', 'COMPLETE', ?, ?)
                """,
                (
                    row["job_id"],
                    now,
                    json.dumps({"simulated": True, "workflow_action": "COMPLETE_QUALITY_CHECK"}),
                ),
            )

        outcomes = self._refresh_pending_decisions(row["job_id"])
        selected_outcome = outcomes.get(row["decision_id"], "NEEDS_REVIEW")
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO audit_events (
                    entity_type, entity_id, event_type, actor_type, actor_id,
                    details_json, created_at
                ) VALUES ('REVIEW', ?, 'WORKFLOW_STAGE_COMPLETED',
                          'MANAGER', ?, ?, ?)
                """,
                (
                    review_id,
                    actor_id,
                    json.dumps({
                        "job_id": row["job_id"],
                        "action": "COMPLETE_QUALITY_CHECK",
                        "previous_stage": row["current_stage"],
                        "new_stage": "READY_FOR_COLLECTION",
                        "completed_by_role": actor_role,
                        "simulated": True,
                        "outcome": selected_outcome,
                    }),
                    now,
                ),
            )
        return {
            "status": "simulated",
            "review_id": review_id,
            "outcome": selected_outcome,
            "workflow_stage": "READY_FOR_COLLECTION",
            "workflow_owner": "SERVICE_ADVISER",
        }

    def reset_workflow_demo(
        self,
        review_id: str,
        actor_id: str = "demo-manager",
    ) -> dict[str, object]:
        with self.database.session() as connection:
            row = connection.execute(
                """
                SELECT r.status AS review_status, conv.job_id,
                       sj.current_stage, sj.current_owner_role, sj.version
                FROM reviews r
                JOIN decisions d ON d.id = r.decision_id
                JOIN messages m ON m.id = d.message_id
                JOIN conversations conv ON conv.id = m.conversation_id
                JOIN service_jobs sj ON sj.id = conv.job_id
                WHERE r.id = ?
                """,
                (review_id,),
            ).fetchone()
        if row is None:
            raise LookupError("Review not found")
        if row["review_status"] != "PENDING":
            raise ValueError("Reset the workflow before approving or rejecting the review")
        if row["current_stage"] == "QUALITY_CHECK_PENDING":
            return {"status": "already_reset", "review_id": review_id}

        now = utc_now()
        with self.database.transaction() as connection:
            updated = connection.execute(
                """
                UPDATE service_jobs
                SET current_stage = 'QUALITY_CHECK_PENDING',
                    current_owner_role = 'QUALITY_CONTROLLER',
                    version = version + 1, workflow_updated_at = ?
                WHERE id = ? AND version = ?
                """,
                (now, row["job_id"], row["version"]),
            )
            if updated.rowcount != 1:
                raise ValueError("The job changed while the reset was being applied; refresh and retry")
            connection.execute(
                """
                INSERT INTO workflow_events (
                    job_id, previous_stage, new_stage, action, completed_by,
                    completed_by_role, previous_owner_role, next_owner_role,
                    notes, simulated, created_at
                ) VALUES (?, ?, 'QUALITY_CHECK_PENDING', 'RESET_SYNTHETIC_SCENARIO', ?,
                          'MANAGER', ?, 'QUALITY_CONTROLLER',
                          'Reset synthetic workflow demonstration', 1, ?)
                """,
                (
                    row["job_id"], row["current_stage"], actor_id,
                    row["current_owner_role"], now,
                ),
            )
            connection.execute(
                """
                INSERT INTO job_status_events (
                    job_id, source, status_type, status_value,
                    observed_at, raw_payload_json
                ) VALUES (?, 'QUALITY_CONTROL', 'QUALITY_CHECK', 'PENDING', ?, ?)
                """,
                (
                    row["job_id"],
                    now,
                    json.dumps({"simulated": True, "workflow_action": "RESET_SYNTHETIC_SCENARIO"}),
                ),
            )

        self._refresh_pending_decisions(row["job_id"])
        return {
            "status": "reset",
            "review_id": review_id,
            "workflow_stage": "QUALITY_CHECK_PENDING",
            "workflow_owner": "QUALITY_CONTROLLER",
        }

    def _refresh_pending_decisions(self, job_id: str) -> dict[str, str]:
        with self.database.session() as connection:
            decisions = connection.execute(
                """
                SELECT d.id AS decision_id, d.proposed_response,
                       cl.intent, m.language
                FROM decisions d
                JOIN reviews r ON r.decision_id = d.id
                JOIN messages m ON m.id = d.message_id
                JOIN classifications cl ON cl.message_id = m.id
                JOIN conversations conv ON conv.id = m.conversation_id
                WHERE conv.job_id = ? AND r.status = 'PENDING'
                """,
                (job_id,),
            ).fetchall()

        outcomes: dict[str, str] = {}
        for decision in decisions:
            result = self._evaluate_rules(
                job_id=job_id,
                intent=decision["intent"],
                agent_response=decision["proposed_response"],
                language=decision["language"] or "English",
            )
            outcomes[decision["decision_id"]] = str(result["outcome"])
            with self.database.transaction() as connection:
                connection.execute(
                    """
                    UPDATE decisions
                    SET outcome = ?, justification = ?, proposed_response = ?,
                        rules_triggered_json = ?, rule_version = 'c01-v3'
                    WHERE id = ?
                    """,
                    (
                        result["outcome"], result["justification"],
                        result["proposed_response"], json.dumps(result["rules"]),
                        decision["decision_id"],
                    ),
                )
                connection.execute(
                    "DELETE FROM decision_evidence WHERE decision_id = ?",
                    (decision["decision_id"],),
                )
                for evidence in result["evidence"]:
                    is_workflow_state = evidence["source"] == "AUTHORITATIVE_WORKFLOW"
                    connection.execute(
                        """
                        INSERT INTO decision_evidence (
                            decision_id, source_type, source_record_id, field_name,
                            captured_value, observed_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            decision["decision_id"],
                            "WORKFLOW_STATE" if is_workflow_state else "JOB_STATUS_EVENT",
                            f"{job_id}:{evidence['source']}:{evidence['status_type']}",
                            "current_stage" if is_workflow_state else "status_value",
                            evidence["status_value"], evidence["observed_at"],
                        ),
                    )
        return outcomes

    def list_vehicle_workflows(self, query: str = "") -> list[dict[str, object]]:
        pattern = f"%{query.strip().upper()}%"
        with self.database.session() as connection:
            rows = connection.execute(
                """
                SELECT sj.id AS job_id, sj.current_stage, sj.current_owner_role,
                       sj.version, sj.workflow_updated_at,
                       v.registration_normalized, v.make, v.model,
                       c.id AS customer_id
                FROM service_jobs sj
                JOIN vehicles v ON v.id = sj.vehicle_id
                JOIN customers c ON c.id = v.customer_id
                WHERE ? = '%%'
                   OR UPPER(sj.id) LIKE ?
                   OR UPPER(v.registration_normalized) LIKE ?
                   OR UPPER(c.id) LIKE ?
                ORDER BY sj.workflow_updated_at DESC, sj.id
                """,
                (pattern, pattern, pattern, pattern),
            ).fetchall()
        return [
            {
                "jobId": row["job_id"],
                "registration": row["registration_normalized"],
                "customerId": row["customer_id"],
                "vehicle": f"{row['make'] or 'Vehicle'} {row['model'] or ''}".strip(),
                "currentStage": (row["current_stage"] or "UNKNOWN").replace("_", " ").title(),
                "currentOwnerRole": (row["current_owner_role"] or "UNASSIGNED").replace("_", " ").title(),
                "version": row["version"],
                "updatedAt": row["workflow_updated_at"],
            }
            for row in rows
        ]

    def get_vehicle_workflow(self, job_id: str) -> dict[str, object] | None:
        with self.database.session() as connection:
            job = connection.execute(
                """
                SELECT sj.id AS job_id, sj.current_stage, sj.current_owner_role,
                       sj.version, sj.workflow_updated_at,
                       v.registration_normalized, v.make, v.model,
                       c.id AS customer_id
                FROM service_jobs sj
                JOIN vehicles v ON v.id = sj.vehicle_id
                JOIN customers c ON c.id = v.customer_id
                WHERE sj.id = ?
                """,
                (job_id,),
            ).fetchone()
            if job is None:
                return None
            events = connection.execute(
                """
                SELECT previous_stage, new_stage, action, completed_by,
                       completed_by_role, previous_owner_role, next_owner_role,
                       notes, simulated, created_at
                FROM workflow_events
                WHERE job_id = ? ORDER BY id DESC
                """,
                (job_id,),
            ).fetchall()
            actions = connection.execute(
                """
                SELECT action, required_role, next_stage, next_owner_role
                FROM workflow_stage_rules WHERE current_stage = ? ORDER BY action
                """,
                (job["current_stage"],),
            ).fetchall()
        return {
            "jobId": job["job_id"],
            "registration": job["registration_normalized"],
            "customerId": job["customer_id"],
            "vehicle": f"{job['make'] or 'Vehicle'} {job['model'] or ''}".strip(),
            "currentStage": (job["current_stage"] or "UNKNOWN").replace("_", " ").title(),
            "currentStageCode": job["current_stage"],
            "currentOwnerRole": (job["current_owner_role"] or "UNASSIGNED").replace("_", " ").title(),
            "currentOwnerRoleCode": job["current_owner_role"],
            "version": job["version"],
            "updatedAt": job["workflow_updated_at"],
            "allowedActions": [
                {
                    "action": action["action"],
                    "label": action["action"].replace("_", " ").title(),
                    "requiredRole": action["required_role"],
                    "requiredRoleLabel": action["required_role"].replace("_", " ").title(),
                    "nextStage": action["next_stage"].replace("_", " ").title(),
                    "nextOwnerRole": action["next_owner_role"].replace("_", " ").title(),
                }
                for action in actions
            ],
            "history": [
                {
                    "previousStage": (event["previous_stage"] or "Start").replace("_", " ").title(),
                    "newStage": event["new_stage"].replace("_", " ").title(),
                    "action": event["action"].replace("_", " ").title(),
                    "completedBy": event["completed_by"],
                    "completedByRole": event["completed_by_role"].replace("_", " ").title(),
                    "nextOwnerRole": event["next_owner_role"].replace("_", " ").title(),
                    "notes": event["notes"],
                    "simulated": bool(event["simulated"]),
                    "createdAt": event["created_at"],
                }
                for event in events
            ],
        }

    def transition_vehicle_workflow(
        self,
        *,
        job_id: str,
        action: str,
        actor_role: str,
        actor_id: str = "demo-workflow-user",
    ) -> dict[str, object]:
        with self.database.transaction() as connection:
            job = connection.execute(
                """
                SELECT current_stage, current_owner_role, version
                FROM service_jobs WHERE id = ?
                """,
                (job_id,),
            ).fetchone()
            if job is None:
                raise LookupError("Service job not found")
            transition = connection.execute(
                """
                SELECT required_role, next_stage, next_owner_role
                FROM workflow_stage_rules
                WHERE current_stage = ? AND action = ?
                """,
                (job["current_stage"], action),
            ).fetchone()
            if transition is None:
                raise ValueError("This action is not allowed from the current stage")
            if actor_role != transition["required_role"] or actor_role != job["current_owner_role"]:
                raise ValueError(
                    f"Only the assigned {transition['required_role'].replace('_', ' ').title()} can perform this action"
                )
            now = utc_now()
            updated = connection.execute(
                """
                UPDATE service_jobs
                SET current_stage = ?, current_owner_role = ?,
                    version = version + 1, workflow_updated_at = ?
                WHERE id = ? AND current_stage = ?
                  AND current_owner_role = ? AND version = ?
                """,
                (
                    transition["next_stage"], transition["next_owner_role"], now,
                    job_id, job["current_stage"], job["current_owner_role"], job["version"],
                ),
            )
            if updated.rowcount != 1:
                raise ValueError("The job changed while this action was being applied; refresh and retry")
            connection.execute(
                """
                INSERT INTO workflow_events (
                    job_id, previous_stage, new_stage, action, completed_by,
                    completed_by_role, previous_owner_role, next_owner_role,
                    notes, simulated, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                          'Synthetic role-authorized workflow transition', 1, ?)
                """,
                (
                    job_id, job["current_stage"], transition["next_stage"], action,
                    actor_id, actor_role, job["current_owner_role"],
                    transition["next_owner_role"], now,
                ),
            )
            if action == "COMPLETE_QUALITY_CHECK":
                connection.execute(
                    """
                    INSERT INTO job_status_events (
                        job_id, source, status_type, status_value,
                        observed_at, raw_payload_json
                    ) VALUES (?, 'QUALITY_CONTROL', 'QUALITY_CHECK', 'COMPLETE', ?, ?)
                    """,
                    (job_id, now, json.dumps({"simulated": True, "workflow_action": action})),
                )
        self._refresh_pending_decisions(job_id)
        return self.get_vehicle_workflow(job_id) or {}

    def reset_vehicle_workflow_demo(self, job_id: str) -> dict[str, object]:
        with self.database.session() as connection:
            review = connection.execute(
                """
                SELECT r.id
                FROM reviews r
                JOIN decisions d ON d.id = r.decision_id
                JOIN messages m ON m.id = d.message_id
                JOIN conversations conv ON conv.id = m.conversation_id
                WHERE conv.job_id = ? AND r.status = 'PENDING'
                ORDER BY r.created_at DESC LIMIT 1
                """,
                (job_id,),
            ).fetchone()
        if review is None:
            raise ValueError("This demonstration requires at least one pending inquiry")
        self.reset_workflow_demo(review["id"])
        return self.get_vehicle_workflow(job_id) or {}

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
                       sj.id AS job_id, sj.current_stage, sj.current_owner_role,
                       sj.version AS workflow_version, v.registration_normalized,
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
                elif row["outcome"] in {"ANSWER", "CALLBACK"}:
                    ui_status = "ready"
                else:
                    ui_status = "needs_review"
                if ui_status == "sent":
                    next_action = "Response delivered; retain the case for audit history"
                    next_action_owner = "Service adviser"
                    uncertainty = "Resolved"
                elif row["current_stage"] == "READY_FOR_COLLECTION":
                    next_action = "Review and approve the collection confirmation"
                    next_action_owner = "Service adviser"
                    uncertainty = "Evidence aligned; final adviser approval is still required"
                elif ui_status == "rejected":
                    next_action = "Revise the proposed response and reassess the evidence"
                    next_action_owner = "Service adviser"
                    uncertainty = "Manager requested a revision"
                elif row["current_stage"] == "QUALITY_CHECK_PENDING":
                    next_action = "Complete the assigned quality-control stage"
                    next_action_owner = "Quality controller"
                    uncertainty = "CRM reports ready, but the authoritative workflow is still in quality control"
                else:
                    next_action = "Complete the currently assigned workflow stage"
                    next_action_owner = (row["current_owner_role"] or "Unassigned").replace("_", " ").title()
                    uncertainty = "The workflow has not reached collection confirmation"
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
                    "nextAction": next_action,
                    "nextActionOwner": next_action_owner,
                    "uncertainty": uncertainty,
                    "workflowStage": (row["current_stage"] or "UNKNOWN").replace("_", " ").title(),
                    "workflowOwner": (row["current_owner_role"] or "UNASSIGNED").replace("_", " ").title(),
                    "workflowVersion": row["workflow_version"] or 1,
                    "canCompleteQualityCheck": (
                        row["review_status"] == "PENDING"
                        and row["intent"] in {"COLLECTION_STATUS", "REPAIR_STATUS"}
                        and row["current_stage"] == "QUALITY_CHECK_PENDING"
                        and row["current_owner_role"] == "QUALITY_CONTROLLER"
                    ),
                    "canResetWorkflowDemo": (
                        row["review_status"] == "PENDING"
                        and row["intent"] in {"COLLECTION_STATUS", "REPAIR_STATUS"}
                        and row["current_stage"] == "READY_FOR_COLLECTION"
                    ),
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
