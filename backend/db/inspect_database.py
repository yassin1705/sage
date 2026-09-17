from __future__ import annotations

from .database import Database
from .repositories import CaseRepository


def main() -> None:
    database = Database()
    repository = CaseRepository(database)

    print(f"Database: {database.path}")
    for case in repository.list_review_cases():
        print(
            f"{case.review_id}: {case.customer_id} / {case.job_id} / "
            f"{case.classification} / {case.review_status}"
        )


if __name__ == "__main__":
    main()
