from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from backend.agent import QwenAgent
from backend.config import AgentConfig, load_gmail_config
from backend.db import Database
from backend.db.seed import seed_database
from backend.integrations import GmailSender
from backend.services import WorkflowService


class WorkflowTransitionTest(unittest.TestCase):
    def test_only_assigned_role_can_complete_quality_control(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "test.db")
            seed_database(database)
            service = WorkflowService(
                database,
                QwenAgent(AgentConfig(False, "http://127.0.0.1:11434", "qwen3:8b", 1, "0")),
                GmailSender(load_gmail_config()),
            )
            created = asyncio.run(service.create_customer_request(
                customer_id="CUS-A",
                registration="ABC-123",
                delivery_email="customer@example.com",
                consent=True,
                language="English",
                message="Can I collect my car today?",
            ))

            with self.assertRaisesRegex(ValueError, "Only the quality controller"):
                service.complete_quality_check_transition(
                    created["review_id"],
                    actor_role="TECHNICIAN",
                )

            result = service.complete_quality_check_transition(created["review_id"])
            inquiry = next(
                item for item in service.list_manager_inquiries()
                if item["id"] == created["review_id"]
            )
            with database.session() as connection:
                job = connection.execute(
                    """
                    SELECT current_stage, current_owner_role, version
                    FROM service_jobs WHERE id = 'JOB-1'
                    """
                ).fetchone()
                events = connection.execute(
                    """
                    SELECT previous_stage, new_stage, completed_by_role
                    FROM workflow_events WHERE job_id = 'JOB-1' ORDER BY id
                    """
                ).fetchall()

            self.assertEqual("ANSWER", result["outcome"])
            self.assertEqual("READY_FOR_COLLECTION", job["current_stage"])
            self.assertEqual("SERVICE_ADVISER", job["current_owner_role"])
            self.assertEqual(2, job["version"])
            self.assertEqual(2, len(events))
            self.assertEqual("QUALITY_CONTROLLER", events[-1]["completed_by_role"])
            self.assertEqual("ready", inquiry["status"])
            self.assertEqual("Service Adviser", inquiry["workflowOwner"])

            reset = service.reset_workflow_demo(created["review_id"])
            reset_inquiry = next(
                item for item in service.list_manager_inquiries()
                if item["id"] == created["review_id"]
            )
            with database.session() as connection:
                reset_job = connection.execute(
                    """
                    SELECT current_stage, current_owner_role, version
                    FROM service_jobs WHERE id = 'JOB-1'
                    """
                ).fetchone()
                event_count = connection.execute(
                    "SELECT COUNT(*) AS count FROM workflow_events WHERE job_id = 'JOB-1'"
                ).fetchone()["count"]

            self.assertEqual("reset", reset["status"])
            self.assertEqual("QUALITY_CHECK_PENDING", reset_job["current_stage"])
            self.assertEqual("QUALITY_CONTROLLER", reset_job["current_owner_role"])
            self.assertEqual(3, reset_job["version"])
            self.assertEqual(3, event_count)
            self.assertEqual("needs_review", reset_inquiry["status"])
            self.assertTrue(reset_inquiry["canCompleteQualityCheck"])


if __name__ == "__main__":
    unittest.main()
