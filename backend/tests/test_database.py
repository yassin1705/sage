from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.db.database import Database
from backend.db.repositories import CaseRepository
from backend.db.seed import seed_database


class DatabaseTest(unittest.TestCase):
    def test_seed_is_repeatable_and_review_cases_are_queryable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "test.db")
            seed_database(database)
            seed_database(database)

            repository = CaseRepository(database)
            cases = repository.list_review_cases()

            self.assertEqual(3, len(cases))
            first_case = repository.get_review_case("REVIEW-1")
            self.assertIsNotNone(first_case)
            assert first_case is not None
            self.assertEqual("CUS-A", first_case.customer_id)
            self.assertEqual("COLLECTION_STATUS", first_case.classification)
            self.assertEqual("NEEDS_REVIEW", first_case.outcome)
            self.assertIn("CONFLICTING_JOB_STATES", first_case.rules_triggered)


if __name__ == "__main__":
    unittest.main()
