from app.llm import complete_json
from app.schemas import ICP

SYSTEM = """You turn a plain description of a target customer into a structured ideal customer profile (ICP) for B2B cold outreach.
Rules:
- Use only what the user wrote plus obvious, conservative implications. Do not invent specifics such as company names or statistics.
- If something is not stated, leave it empty instead of guessing.
- Keep each list short (at most 6 items) and each item a few words.
- target_roles are job titles of the people to contact, for example 'Head of Operations'."""


def parse_icp(product_pitch: str, icp_description: str) -> ICP:
    user = f"What we sell: {product_pitch or '(not provided)'}\n\nWho we want to reach: {icp_description}"
    return complete_json(SYSTEM, user, ICP, temperature=0.1)
