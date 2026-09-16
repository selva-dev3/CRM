from __future__ import annotations

from enum import StrEnum
from typing import Any


class AIDataClass(StrEnum):
    SAFE_OPERATIONAL = "safe_operational"
    SENSITIVE_PURPOSE_RESTRICTED = "sensitive_purpose_restricted"
    NEVER_EXPORT = "never_export"


class AIDataClassificationService:
    """One provider-boundary policy for CRM data minimization.

    Callers may permit a sensitive field only when the user request has an
    explicit business purpose and normal CRM authorization has already passed.
    Never-export fields cannot be overridden.
    """

    NEVER_EXPORT_FIELDS = frozenset(
        {
            "password",
            "password_hash",
            "hashed_password",
            "access_token",
            "refresh_token",
            "id_token",
            "api_key",
            "api_key_hash",
            "secret",
            "client_secret",
            "authorization",
            "cookie",
            "session_id",
            "mfa_secret",
            "two_factor_secret",
            "security_answer",
            "private_key",
            "encryption_key",
            "signing_key",
            "otp_secret",
            "recovery_code",
            "custom_fields",
            "organization_id",
            "tenant_id",
        }
    )
    SENSITIVE_FIELDS = frozenset(
        {
            "email",
            "emails",
            "email_address",
            "phone",
            "phone_number",
            "mobile",
            "body",
            "email_body",
            "content",
            "note",
            "notes",
            "call_notes",
            "description",
            "meeting_description",
            "address",
            "billing_address",
            "shipping_address",
            "date_of_birth",
            "personal_information",
            "user_prompt",
            "ai_response",
            "transcript",
            "contract_text",
            "question",
            "message",
            "history",
            "recent_conversation",
            "natural_language_query",
            "request",
            "user_context",
            "text",
            "objection",
            "social_security_number",
            "ssn",
            "tax_id",
            "tax_number",
            "bank_account",
            "account_number",
            "routing_number",
            "iban",
            "credit_card",
        }
    )

    PURPOSE_ALLOWED_FIELDS: dict[str, frozenset[str]] = {
        "sales_assistant_chat": frozenset({"message", "history"}),
        "sales_assistant_plan": frozenset(
            {"question", "recent_conversation", "user_prompt", "ai_response"}
        ),
        "sales_assistant_answer": frozenset(
            {"question", "recent_conversation", "user_prompt", "ai_response"}
        ),
        "crm_search": frozenset({"natural_language_query"}),
        "email_intelligence": frozenset({"request", "user_context", "content", "body"}),
        "call_intelligence": frozenset({"transcript"}),
        "meeting_intelligence": frozenset({"transcript", "description"}),
        "sentiment_analysis": frozenset({"text"}),
        "objection_handler": frozenset({"objection"}),
        "contract_intelligence": frozenset({"contract_text"}),
    }

    @classmethod
    def classify(cls, field_name: str) -> AIDataClass:
        normalized = field_name.strip().lower()
        if normalized in cls.NEVER_EXPORT_FIELDS or any(
            marker in normalized for marker in ("password", "token", "secret", "credential")
        ):
            return AIDataClass.NEVER_EXPORT
        if normalized in cls.SENSITIVE_FIELDS or normalized.endswith(
            ("_email", "_phone", "_address")
        ):
            return AIDataClass.SENSITIVE_PURPOSE_RESTRICTED
        return AIDataClass.SAFE_OPERATIONAL

    @classmethod
    def minimize(
        cls,
        value: Any,
        *,
        allowed_sensitive_fields: set[str] | frozenset[str] = frozenset(),
    ) -> Any:
        allowed = {field.lower() for field in allowed_sensitive_fields}
        if isinstance(value, dict):
            minimized: dict[str, Any] = {}
            for raw_key, item in value.items():
                key = str(raw_key)
                classification = cls.classify(key)
                if classification is AIDataClass.NEVER_EXPORT:
                    continue
                sensitive_allowed = key.lower() in allowed or any(
                    key.lower().endswith(suffix) and field in allowed
                    for suffix, field in (
                        ("_email", "email"),
                        ("_phone", "phone"),
                        ("_address", "address"),
                    )
                )
                if (
                    classification is AIDataClass.SENSITIVE_PURPOSE_RESTRICTED
                    and not sensitive_allowed
                ):
                    continue
                minimized[key] = cls.minimize(item, allowed_sensitive_fields=allowed)
            return minimized
        if isinstance(value, list):
            return [cls.minimize(item, allowed_sensitive_fields=allowed) for item in value]
        if isinstance(value, tuple):
            return [cls.minimize(item, allowed_sensitive_fields=allowed) for item in value]
        return value

    @classmethod
    def minimize_for_provider(
        cls,
        value: Any,
        *,
        purpose: str,
        requested_sensitive_fields: set[str] | frozenset[str] = frozenset(),
    ) -> Any:
        """Apply one purpose-declared policy immediately before a provider call."""
        allowed = set(cls.PURPOSE_ALLOWED_FIELDS.get(purpose, frozenset()))
        allowed.update(field.lower() for field in requested_sensitive_fields)
        return cls.minimize(value, allowed_sensitive_fields=allowed)

    @classmethod
    def requested_sensitive_fields(cls, message: str) -> set[str]:
        """Return only fields explicitly named by the user's current request."""
        normalized = message.lower()
        aliases = {
            "email": ("email", "mail address"),
            "phone": ("phone", "mobile", "telephone"),
            "notes": ("note", "notes"),
            "call_notes": ("call note", "call notes"),
            "description": ("description",),
            "body": ("email body", "message body"),
            "address": ("address",),
            "user_prompt": ("previous", "earlier", "above", "those", "ones"),
            "ai_response": ("previous", "earlier", "above", "those", "ones"),
        }
        return {
            field
            for field, terms in aliases.items()
            if any(term in normalized for term in terms)
        }

    @classmethod
    def persistence_references(cls, result_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Store safe references and summaries, never complete CRM result bodies."""
        safe_record_fields = {
            "id",
            "name",
            "title",
            "status",
            "stage",
            "amount",
            "due_date",
            "expected_close_date",
            "created_at",
            "updated_at",
        }
        persisted: list[dict[str, Any]] = []
        for block in result_blocks:
            records = []
            for record in block.get("results", []):
                if isinstance(record, dict):
                    records.append(
                        {key: value for key, value in record.items() if key in safe_record_fields}
                    )
            persisted.append(
                {
                    key: value
                    for key, value in block.items()
                    if key in {"key", "title", "entity_type", "intent", "result_count", "explanation", "generated_at"}
                }
                | {"results": records}
            )
        return persisted


ai_data_classification_service = AIDataClassificationService()
