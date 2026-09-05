from app.db.base import Base
from app.models.ai import (
    AIAction,
    AIConversation,
    AIGeneratedContent,
    AILeadScore,
    AIMeetingSummary,
    AIOrganizationConfig,
    AIPrompt,
    AIRun,
    AITranscript,
)
from app.models.audit import ActivityLog, AuditLog
from app.models.auth import (
    EmailVerification,
    MagicLinkToken,
    OTPVerification,
    PasswordReset,
    RefreshToken,
    UserProfile,
    UserSession,
)
from app.models.calendar import CalendarEventModel
from app.models.call import CallLog
from app.models.company import Company, CompanyContact
from app.models.contact import Contact, ContactAddress, ContactTag
from app.models.deal import Deal, DealActivity, DealProduct, DealStage, DealStageHistory
from app.models.document import Document, DocumentVersion
from app.models.email import Email, EmailLog, EmailTemplate
from app.models.integration import ApiKey, Integration, Webhook
from app.models.invoice import Invoice, InvoiceItem
from app.models.lead import (
    Lead,
    LeadActivity,
    LeadAttachment,
    LeadNote,
    LeadScore,
    LeadSource,
    LeadStatus,
    LeadTag,
)
from app.models.meeting import Meeting, MeetingAttendee
from app.models.note import Note
from app.models.notification import Notification
from app.models.organization import (
    Organization,
    OrganizationInvitation,
    OrganizationSetting,
    OrganizationSubscription,
    ProcessedWebhookEvent,
    SubscriptionPlan,
)
from app.models.payment import Payment
from app.models.product import Product, ProductCategory
from app.models.project import Project
from app.models.quote import Quote, QuoteItem
from app.models.quote_delivery import QuoteDeliveryAttempt
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.report import CustomReport, ReportExport, ScheduledReport
from app.models.system import (
    City,
    Country,
    Currency,
    CustomField,
    FileUpload,
    Language,
    SLAPolicy,
    State,
    SystemSetting,
    Timezone,
)
from app.models.task import Task, TaskAttachment, TaskComment
from app.models.user import User, UserInvitation
from app.models.user_quota import UserQuota

__all__ = [
    "Payment",
    "Base",
    "Organization",
    "OrganizationSetting",
    "OrganizationSubscription",
    "SubscriptionPlan",
    "OrganizationInvitation",
    "ProcessedWebhookEvent",
    "User",
    "UserInvitation",
    "UserProfile",
    "UserSession",
    "RefreshToken",
    "PasswordReset",
    "MagicLinkToken",
    "EmailVerification",
    "OTPVerification",
    "Role",
    "Permission",
    "RolePermission",
    "UserRole",
    "Lead",
    "LeadSource",
    "LeadStatus",
    "LeadScore",
    "LeadTag",
    "LeadActivity",
    "LeadNote",
    "LeadAttachment",
    "Contact",
    "ContactAddress",
    "ContactTag",
    "Company",
    "CompanyContact",
    "Deal",
    "DealStage",
    "DealActivity",
    "DealStageHistory",
    "DealProduct",
    "UserQuota",
    "Task",
    "TaskComment",
    "TaskAttachment",
    "Meeting",
    "MeetingAttendee",
    "CallLog",
    "Email",
    "EmailTemplate",
    "EmailLog",
    "Note",
    "Document",
    "DocumentVersion",
    "ProductCategory",
    "Product",
    "Quote",
    "QuoteItem",
    "QuoteDeliveryAttempt",
    "Invoice",
    "InvoiceItem",
    "Notification",
    "CalendarEventModel",
    "ReportExport",
    "CustomReport",
    "ScheduledReport",
    "AuditLog",
    "ActivityLog",
    "Integration",
    "ApiKey",
    "Webhook",
    "AIConversation",
    "AIAction",
    "AIPrompt",
    "AIGeneratedContent",
    "AILeadScore",
    "AIMeetingSummary",
    "AIOrganizationConfig",
    "AIRun",
    "AITranscript",
    "SystemSetting",
    "CustomField",
    "SLAPolicy",
    "FileUpload",
    "Country",
    "State",
    "City",
    "Currency",
    "Language",
    "Timezone",
    "Project",
]
