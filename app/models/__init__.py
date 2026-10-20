"""Import all ORM models so they register on Base.metadata."""
from app.models.event import Event
from app.models.ledger import (
    Customer,
    Job,
    Machine,
    ServiceRequest,
    Task,
    Visit,
)
from app.models.ops import (
    ActionRegister,
    Alert,
    Conversation,
    Message,
    Payment,
    RuleViolation,
    Setting,
    Takeover,
)
from app.models.people import ServicePartner, Technician

__all__ = [
    "Event",
    "Customer",
    "Machine",
    "Job",
    "Visit",
    "Task",
    "ServiceRequest",
    "ServicePartner",
    "Technician",
    "Payment",
    "ActionRegister",
    "Alert",
    "Takeover",
    "RuleViolation",
    "Conversation",
    "Setting",
    "Message",
]
