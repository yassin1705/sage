from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

from backend.agent import QwenAgent
from backend.config import load_agent_config, load_gmail_config
from backend.db import Database
from backend.db.seed import seed_database
from backend.integrations import GmailSender
from backend.services import WorkflowService


class CustomerRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=50)
    registration: str = Field(min_length=2, max_length=30)
    email: EmailStr
    consent: bool
    message: str = Field(min_length=2, max_length=4000)


class ApproveReviewRequest(BaseModel):
    final_response: str = Field(min_length=2, max_length=8000)
    classification: str = Field(min_length=2, max_length=100)


class RejectReviewRequest(BaseModel):
    note: str = Field(default="Manager rejected the proposed decision", max_length=2000)


database = Database()
seed_database(database)
gmail_config = load_gmail_config()
agent_config = load_agent_config()
workflow = WorkflowService(
    database=database,
    agent=QwenAgent(agent_config),
    gmail=GmailSender(gmail_config),
)

app = FastAPI(title="SAGE API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "gmail_mode": gmail_config.mode,
        "agent_model": agent_config.model,
        "agent_enabled": agent_config.enabled,
    }


@app.post("/api/customer/requests", status_code=201)
async def create_customer_request(request: CustomerRequest) -> dict[str, object]:
    try:
        return await workflow.create_customer_request(
            customer_id=request.customer_id,
            registration=request.registration,
            delivery_email=str(request.email),
            consent=request.consent,
            message=request.message,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/customer/cases/{conversation_id}")
def get_customer_case(conversation_id: str) -> dict[str, object]:
    result = workflow.get_customer_case(conversation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Customer case not found")
    return result


@app.get("/api/manager/inquiries")
def list_manager_inquiries() -> list[dict[str, object]]:
    return workflow.list_manager_inquiries()


@app.post("/api/manager/reviews/{review_id}/approve")
def approve_review(review_id: str, request: ApproveReviewRequest) -> dict[str, object]:
    try:
        return workflow.approve_review(
            review_id=review_id,
            final_response=request.final_response,
            classification_label=request.classification,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/api/manager/reviews/{review_id}/reject")
def reject_review(review_id: str, request: RejectReviewRequest) -> dict[str, str]:
    try:
        workflow.reject_review(review_id, request.note)
        return {"status": "rejected", "review_id": review_id}
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/connections/gmail")
def gmail_connection() -> dict[str, object]:
    return {
        "mode": gmail_config.mode,
        "live": gmail_config.is_live,
        "sender_name": gmail_config.sender_name,
        "authorized": gmail_config.token_file.exists() if gmail_config.is_live else False,
    }
