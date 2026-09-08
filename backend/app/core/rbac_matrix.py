"""Approved system-role grants. Permission identity is the key, never its label."""


def _keys(spec: str) -> frozenset[str]:
    return frozenset(
        f"{module}:{action}"
        for line in spec.strip().splitlines()
        for module, actions in [line.strip().split(" ", 1)]
        for action in actions.split()
    )


ADMIN_PERMISSIONS = _keys("""
dashboard read customize export
leads read create update delete export import assign convert bulk_delete bulk_update
contacts read create update delete export import assign bulk_delete bulk_update
companies read create update delete export import bulk_delete
deals read create update delete pipeline export import assign bulk_delete
tasks read create update delete assign complete export import
meetings read create update delete invite export
calls read create update delete recording
emails read send templates delete
notes read create update delete
documents read upload delete share
products read create update delete export import
quotes read create update approve delete send export import
invoices read create update send delete payment export import
reports read create export schedule delete
calendar read write sync
users read create invite update delete export import roles reset_password assign_roles
roles read create update delete assign
organization read update billing domains branding audit members transfer_ownership
invitations read create resend revoke
integrations read manage apikeys
notifications read manage send
settings read update security
activities read create export
ai read generate configure
api_keys read create revoke
projects read create update delete assign
""")

SYSTEM_ROLE_PERMISSIONS = {
    "Admin": ADMIN_PERMISSIONS,
    "Sales Manager": _keys("""
dashboard read customize export
leads read create update delete export import assign convert bulk_delete bulk_update
contacts read create update delete export import assign bulk_delete bulk_update
companies read create update delete export import bulk_delete
deals read create update delete pipeline export import assign bulk_delete
tasks read create update delete assign complete export import
meetings read create update delete invite export
calls read create update delete recording
emails read send templates
notes read create update delete
documents read upload delete share
products read create update delete export import
quotes read create update approve delete send export import
invoices read create update send delete payment export import
reports read create export schedule
calendar read write sync
activities read create export
ai read generate
projects read create update delete assign
"""),
    "Sales Executive": _keys("""
dashboard read
leads read create update convert export
contacts read create update export
companies read create update
deals read create update pipeline export
tasks read create update complete
meetings read create update invite
calls read create update
emails read send templates
notes read create update
documents read upload share
products read
quotes read update send
invoices read
reports read
calendar read write
activities read create
ai read generate
"""),
    "Marketing Executive": _keys("""
dashboard read
leads read create update import export
contacts read create update import export
companies read
emails read send templates
tasks read create update complete
meetings read create update
calendar read write
reports read export
activities read create
ai read generate
"""),
    "Customer Support": _keys("""
dashboard read
leads read
contacts read update
companies read update
tasks read create update complete
meetings read create update
calls read create update
emails read send
notes read create update
documents read upload
invoices read
calendar read write
activities read create
ai read
"""),
    "Read Only": _keys("""
dashboard read
leads read
contacts read
companies read
deals read
tasks read
meetings read
calls read
emails read
notes read
documents read
products read
quotes read
invoices read
reports read
calendar read
activities read
ai read
projects read
"""),
}

SYSTEM_ROLE_NAMES = frozenset({"Super Admin", *SYSTEM_ROLE_PERMISSIONS})

# This is the authoritative permission-key catalog. Display metadata may live in
# the role service, but authorization and tenant-managed roles must only accept
# keys registered here. Platform authority itself remains controlled by
# ``User.is_platform_admin`` rather than by this delegable permission.
PLATFORM_PERMISSIONS = frozenset({"organization:delete", "super_admin:manage"})
APPROVED_PERMISSION_KEYS = frozenset({*ADMIN_PERMISSIONS, *PLATFORM_PERMISSIONS})


def validate_permission_keys(
    values: list[str] | set[str] | frozenset[str], *, allow_platform: bool = False
) -> list[str]:
    """Return normalized approved keys or raise for unknown/legacy wildcard keys."""
    normalized = list(dict.fromkeys(value.strip().lower() for value in values if value.strip()))
    allowed = APPROVED_PERMISSION_KEYS if allow_platform else ADMIN_PERMISSIONS
    invalid = sorted(set(normalized) - allowed)
    if invalid:
        from app.core.errors import APIException

        raise APIException(
            status_code=422,
            code="INVALID_PERMISSION_KEYS",
            message=f"Unknown or unsupported permission keys: {', '.join(invalid)}",
        )
    return normalized
