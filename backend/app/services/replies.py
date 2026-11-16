"""Store a reply to a sent email and label it with the LLM. The label is a suggestion for the human:
is_hot is forced to false unless the label is interested or question."""
from app import repo
from app.config import settings
from app.llm import LLMError, complete_json
from app.schemas import ReplyClass

SYSTEM = """You label a prospect's reply to a cold sales email. Use only the reply text.
Labels:
- interested: they want to talk, see more, get pricing or a demo, or say yes.
- question: they ask something before deciding (what it costs, how it works, who else uses it).
- not_interested: a polite or blunt no.
- out_of_office: an automatic or personal away message.
- unsubscribe: they ask to be removed or not contacted again.
is_hot is true only when the person shows clear buying intent: they ask for a call, demo, pricing or next steps, or say they want to go ahead.
reason: one sentence quoting or paraphrasing the part of the reply that decided the label."""

SAMPLES = {
    "interested": "Hi, this is timely. We have been looking at this exactly. Can you send pricing and are you free for a call on Thursday?",
    "question": "Thanks for reaching out. How does it work with our existing tools, and do you have customers in our industry?",
    "not_interested": "Thanks, but we are not looking at this right now. Please do not follow up.",
    "out_of_office": "I am out of the office until the 24th with limited access to email. I will reply when I am back.",
    "unsubscribe": "Please remove me from your list and do not contact me again.",
}


def classify(body: str) -> ReplyClass:
    out = complete_json(SYSTEM, f"Reply:\n{body[:3000]}", ReplyClass, model=settings.llm_model_fast or settings.llm_model or None,
                        temperature=0.0, max_tokens=800)
    if out.label not in ("interested", "question"):
        out = out.model_copy(update={"is_hot": False})
    return out


def label_fields(body: str) -> tuple[dict, str | None]:
    """Returns the columns to store and a warning when the model could not label the reply."""
    try:
        c = classify(body)
    except LLMError as exc:
        return {}, str(exc)
    return {"label": c.label, "is_hot": c.is_hot, "reason": c.reason.strip()}, None


def record_reply(user_id: str, lead: dict, body: str, simulated: bool) -> tuple[dict, str | None]:
    """Save the reply (even if labelling fails) and mark the lead as replied."""
    email = repo.get_latest_email(user_id, lead["id"])
    fields, warning = label_fields(body)
    reply = repo.insert_reply(user_id, {
        "lead_id": lead["id"], "campaign_id": lead["campaign_id"], "email_id": email["id"] if email else None,
        "body": body.strip(), "simulated": simulated, **fields,
    })
    repo.update_lead(user_id, lead["id"], {"status": "replied"})
    return reply, warning
