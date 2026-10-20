"""Domain errors. Protective-rule and state-machine violations are first-class."""
from __future__ import annotations


class ResqError(Exception):
    """Base for all domain errors."""


class IllegalTransition(ResqError):
    """An attempt to move a job to a state the machine does not allow."""


class ProtectiveRuleError(ResqError):
    """A protective rule (spec 4.2) blocked the action. Never bypassed by the LLM."""

    def __init__(self, rule: str, detail: str):
        self.rule = rule
        self.detail = detail
        super().__init__(f"[{rule}] {detail}")


class OptInRequired(ProtectiveRuleError):
    def __init__(self, detail: str = "No message without the customer's opt-in."):
        super().__init__("opt_in", detail)


class KillSwitchOn(ResqError):
    """Organisers can stop any build (spec, before production)."""
