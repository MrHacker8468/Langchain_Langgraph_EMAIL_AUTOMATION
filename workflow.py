import os
import smtplib
from typing import Any, TypedDict

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from email_sender import send_email


MODEL_NAME = "gemini-3.6-flash"


class EmailDraft(BaseModel):
    """Email content prepared from the user's request."""

    subject: str = Field(description="A concise email subject line")
    body: str = Field(description="The complete plain-text email body")


class ReviewDecision(BaseModel):
    """A quality decision for the email draft."""

    approved: bool = Field(description="Whether the draft is ready to send")
    feedback: str = Field(description="A short reason for the decision")


class EmailWorkflowState(TypedDict, total=False):
    task: str
    recipient: str
    plan: str
    subject: str
    body: str
    review_approved: bool
    review_feedback: str
    email_sent: bool
    send_error: str
    status: str
    steps: dict[str, str]


def _text_from_content(content: Any) -> str:
    """Extract readable text from either string or block-based model content."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block["text"]
            for block in content
            if isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        ]
        if parts:
            return "\n".join(parts)
    return str(content)


def _step_update(state: EmailWorkflowState, step_name: str, value: str = "complete") -> dict:
    steps = dict(state.get("steps", {}))
    steps[step_name] = value
    return {"steps": steps}


def build_workflow():
    """Build the email workflow graph using Gemini 3.6 Flash."""
    load_dotenv()
    if not os.getenv("GEMINI_API_KEY"):
        raise ValueError("GEMINI_API_KEY is missing. Add it to your .env file.")

    model = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        max_output_tokens=1200,
    )

    plan_chain = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Turn the user's email request into 2 to 4 short planning steps. "
                "Consider the recipient and requested tone. Do not invent facts.",
            ),
            ("human", "Recipient: {recipient}\nEmail request: {task}"),
        ]
    ) | model

    draft_chain = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Write a polished, ready-to-send email that follows the request and "
                "plan. Do not include markdown fences. Do not invent names, dates, "
                "or other facts that the user did not provide.",
            ),
            (
                "human",
                "Recipient: {recipient}\nRequest: {task}\nPlan:\n{plan}",
            ),
        ]
    ) | model.with_structured_output(EmailDraft)

    review_chain = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Check whether this email follows the user's request, is suitable "
                "for the recipient, and contains no unsupported factual claims. "
                "Approve only when it is ready to send. Give one short reason.",
            ),
            (
                "human",
                "Recipient: {recipient}\nRequest: {task}\nSubject: {subject}\n"
                "Email body:\n{body}",
            ),
        ]
    ) | model.with_structured_output(ReviewDecision)

    def plan_email(state: EmailWorkflowState) -> dict:
        response = plan_chain.invoke(
            {"task": state["task"], "recipient": state["recipient"]}
        )
        return {
            "plan": _text_from_content(response.content),
            **_step_update(state, "plan"),
        }

    def draft_email(state: EmailWorkflowState) -> dict:
        draft = draft_chain.invoke(
            {
                "task": state["task"],
                "recipient": state["recipient"],
                "plan": state["plan"],
            }
        )
        return {
            "subject": draft.subject,
            "body": draft.body,
            **_step_update(state, "draft"),
        }

    def review_email(state: EmailWorkflowState) -> dict:
        decision = review_chain.invoke(
            {
                "task": state["task"],
                "recipient": state["recipient"],
                "subject": state["subject"],
                "body": state["body"],
            }
        )
        return {
            "review_approved": decision.approved,
            "review_feedback": decision.feedback,
            **_step_update(state, "review"),
        }

    def send_email_node(state: EmailWorkflowState) -> dict:
        try:
            send_email(
                state["recipient"],
                state["subject"],
                state["body"],
            )
            return {
                "email_sent": True,
                **_step_update(state, "send"),
            }
        except smtplib.SMTPAuthenticationError:
            error = "Gmail sign-in failed. Check SMTP_SENDER_EMAIL and SMTP_APP_PASSWORD."
        except smtplib.SMTPRecipientsRefused:
            error = "Gmail rejected the recipient address. Check the email address."
        except (smtplib.SMTPException, OSError) as exception:
            error = f"Email delivery failed: {exception}"
        except ValueError as exception:
            error = str(exception)
        return {
            "email_sent": False,
            "send_error": error,
            **_step_update(state, "send", "failed"),
        }

    def skip_send(state: EmailWorkflowState) -> dict:
        return {
            "email_sent": False,
            **_step_update(state, "send", "skipped"),
        }

    def set_final_status(state: EmailWorkflowState) -> dict:
        if state.get("email_sent"):
            status = "SENT"
        elif state.get("send_error"):
            status = "FAILED"
        else:
            status = "NEEDS_REVIEW"
        return {"status": status, **_step_update(state, "status")}

    graph = StateGraph(EmailWorkflowState)
    graph.add_node("plan", plan_email)
    graph.add_node("draft", draft_email)
    graph.add_node("review", review_email)
    graph.add_node("send", send_email_node)
    graph.add_node("skip_send", skip_send)
    graph.add_node("status", set_final_status)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "draft")
    graph.add_edge("draft", "review")
    graph.add_conditional_edges(
        "review",
        lambda state: "send" if state["review_approved"] else "skip_send",
        {"send": "send", "skip_send": "skip_send"},
    )
    graph.add_edge("send", "status")
    graph.add_edge("skip_send", "status")
    graph.add_edge("status", END)
    return graph.compile()
