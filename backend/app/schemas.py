from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ICP(BaseModel):
    summary: str = Field(description="One sentence describing the ideal customer.")
    industries: list[str] = Field(default_factory=list)
    company_size: str = Field(default="", description="For example '10-50 employees'. Empty if unknown.")
    regions: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list, description="Job titles of the people to contact.")
    keywords: list[str] = Field(default_factory=list, description="Words likely to appear on a matching company's website.")
    pain_points: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list, description="Kinds of companies to avoid.")


class QueriesOut(BaseModel):
    queries: list[str]


class Candidate(BaseModel):
    company_name: str
    domain: str = Field(description="The company's own website domain, for example acme.com.")
    contact_role: str | None = None


class CandidatesOut(BaseModel):
    companies: list[Candidate] = Field(default_factory=list)


class ResearchOut(BaseModel):
    summary: str = Field(description="At most 60 words, using only the website text.")
    fit_score: int = Field(ge=0, le=100)
    fit_reason: str = Field(description="One sentence.")
    personalization_hook: str | None = Field(default=None, description="One specific detail from the website for an opening line, or null.")


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    product_pitch: str = Field(default="", max_length=2000)
    icp_description: str = Field(min_length=3, max_length=2000)


class CampaignEdit(BaseModel):
    product_pitch: str | None = Field(default=None, max_length=2000)
    icp_description: str | None = Field(default=None, min_length=3, max_length=2000)


class CsvImport(BaseModel):
    csv: str = Field(min_length=1, max_length=400_000)


# ---------- Phase 3: drafting, approval, replies ----------
PLACEHOLDER_MARKERS = ("[", "]", "{{", "}}", "<name>", "<company>")
REPLY_LABELS = ("interested", "question", "not_interested", "out_of_office", "unsubscribe")


class DraftOut(BaseModel):
    subject: str = Field(description="At most 8 words. Plain, specific, no clickbait.")
    body: str = Field(description="The email body, 50 to 150 words, plain text, no signature.")

    @field_validator("subject")
    @classmethod
    def _subject(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v or len(v) > 90:
            raise ValueError("subject must be 1 to 90 characters")
        if any(m in v for m in PLACEHOLDER_MARKERS):
            raise ValueError("subject contains a placeholder such as [Name]; write the real text")
        return v

    @field_validator("body")
    @classmethod
    def _body(cls, v: str) -> str:
        v = v.strip()
        words = len(v.split())
        if words < 30 or words > 220:
            raise ValueError(f"body has {words} words; it must be between 30 and 220")
        if any(m in v for m in PLACEHOLDER_MARKERS):
            raise ValueError("body contains a placeholder such as [Name]; write the real text")
        return v


class EmailEdit(BaseModel):
    subject: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=5000)


class ReplyClass(BaseModel):
    label: Literal["interested", "question", "not_interested", "out_of_office", "unsubscribe"]
    is_hot: bool = Field(description="True only if the person shows clear buying intent.")
    reason: str = Field(description="One sentence explaining the label.")


class ReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class SimulateIn(BaseModel):
    sample: Literal["interested", "question", "not_interested", "out_of_office", "unsubscribe"] = "interested"


# ---------- Phase 4: people and competitors ----------
class PersonOut(BaseModel):
    name: str = Field(description="Full name exactly as written on the page.")
    role: str = Field(default="", description="Job title as written next to the name, or empty.")


class PeopleOut(BaseModel):
    people: list[PersonOut] = Field(default_factory=list)


class CompetitorOut(BaseModel):
    name: str
    domain: str = Field(description="The competitor's own website domain.")
    note: str = Field(default="", description="At most 15 words on what they sell, from the results.")


class CompetitorsOut(BaseModel):
    competitors: list[CompetitorOut] = Field(default_factory=list)
