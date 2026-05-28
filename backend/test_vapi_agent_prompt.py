"""Regression checks for the Vapi system prompt.

The live Vapi agent keeps the in-progress order in model context, so prompt
rules are part of the executable behavior. These checks protect the queue
handoff rule that prevents multi-item orders from being dropped after the
first item gets a quantity.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROMPT = (ROOT / "VAPI_AGENT_DESIGN.md").read_text()


def assert_contains(text: str) -> None:
    assert text in PROMPT, f"missing prompt guardrail: {text}"


def main() -> None:
    assert_contains("[Queued item handoff — after quantity]")
    assert_contains('"Got it. Anything else for today?"')
    assert_contains('call resolve_item("ice cream")')
    assert_contains("Never ask \"Anything else?\" while the queue contains")
    assert_contains("After capturing the final queued item")
    print("Vapi prompt queue handoff guardrails are present.")


if __name__ == "__main__":
    main()
