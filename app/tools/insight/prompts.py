"""Prompt templates for the three Insight modes."""
from __future__ import annotations

SYSTEM = (
    "You are a senior HPE server fleet analyst. You will receive a JSON payload "
    "describing one or more inventories collected from iLO/Redfish: per-server "
    "rows (model, SN, generation, iLO firmware, BIOS, power state, health, "
    "summarized CPU/RAM/storage/NIC/PSU) plus aggregate totals.\n\n"
    "Style guide:\n"
    "- Be thorough — cover everything the payload supports, don't artificially shorten.\n"
    "- Use markdown with clear section headings (## Heading).\n"
    "- Prefer tables for any list of 3+ items; use bullets for short enumerations.\n"
    "- When you cite a specific server, use its hostname or SN.\n"
    "- Numbers and counts: be exact, derive them from the payload.\n"
    "- If the payload doesn't contain a field, say so — don't invent or extrapolate.\n"
    "- Don't hedge with disclaimers; data-center engineers want direct findings."
)

SUMMARY_USER = (
    "Produce a structured health report for this fleet. Cover ALL of the sections below; "
    "each section should have substance, not a one-liner.\n\n"
    "## Headline\n"
    "Total server count, organization mix, model/generation mix in one short paragraph.\n\n"
    "## Health status\n"
    "Breakdown by collection_status (ok/failed/warn) and Redfish `health` field. "
    "If anything is not 'OK', list the affected hosts (hostname + SN + reason).\n\n"
    "## Generation & age profile\n"
    "Which generations are present, in what proportions. Flag anything 3+ generations "
    "behind the newest as aging.\n\n"
    "## Firmware consistency\n"
    "For each model that has 2+ instances, check whether all instances run the same "
    "iLO firmware and BIOS. List models where versions diverge (consistency risk) "
    "with the specific versions seen.\n\n"
    "## Capacity highlights\n"
    "Anything notable in CPU / RAM / storage breakdown — e.g. mixed memory sizes within "
    "the same model, very low or very high RAM-per-host, NIC inconsistency.\n\n"
    "## Top risks\n"
    "Pick the 3-5 most pressing issues and explain WHY each is a risk.\n\n"
    "## Recommended actions\n"
    "Concrete next steps — 4-6 bullets — prioritized.\n\n"
    "Payload:\n```json\n{payload}\n```"
)

ANALYTICS_USER = (
    "Question from operator:\n{question}\n\n"
    "Payload:\n```json\n{payload}\n```\n\n"
    "Answer the question directly. If the payload doesn't contain the "
    "information needed, say so plainly — do not guess."
)

REPORT_TEMPLATES = {
    "procurement": (
        "Build a procurement plan for this fleet:\n"
        "- table grouping servers by model + generation, with count\n"
        "- per-group: typical RAM and storage (so a buyer can match spares)\n"
        "- flag any model that appears once or twice (orphans = hard to spare)\n"
        "- a short note on which generations look due for refresh\n\n"
        "Payload:\n```json\n{payload}\n```"
    ),
    "firmware": (
        "Build a firmware upgrade plan:\n"
        "- table: model | servers affected | current iLO firmware spread | "
        "  current BIOS spread\n"
        "- flag models where firmware varies across instances (consistency risk)\n"
        "- group by upgrade priority (security > stability > nice-to-have)\n\n"
        "Payload:\n```json\n{payload}\n```"
    ),
    "deprecated": (
        "Identify deprecated or end-of-life hardware:\n"
        "- table: hostname | model | generation | iLO gen | why deprecated\n"
        "- group by recommended action (decommission / refresh / keep)\n"
        "- one short paragraph on overall fleet age health\n\n"
        "Payload:\n```json\n{payload}\n```"
    ),
}


def build_messages(
    mode: str,
    *,
    payload_json: str,
    question: str | None = None,
    template: str | None = None,
) -> list[dict]:
    if mode == "summary":
        user = SUMMARY_USER.format(payload=payload_json)
    elif mode == "analytics":
        if not (question or "").strip():
            raise ValueError("analytics mode requires a question")
        user = ANALYTICS_USER.format(question=question.strip(), payload=payload_json)
    elif mode == "reports":
        tpl = REPORT_TEMPLATES.get(template or "")
        if tpl is None:
            raise ValueError(f"unknown report template: {template}")
        user = tpl.format(payload=payload_json)
    else:
        raise ValueError(f"unknown mode: {mode}")

    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
    ]


REPORT_CHOICES = list(REPORT_TEMPLATES.keys())
