import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system_role: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "lower(replace(btrim(name), '_', ' ')) <> 'super admin' OR "
            "(organization_id IS NULL AND is_system_role)",
            name="ck_roles_super_admin_global",
        ),
        Index(
            "uq_roles_platform_super_admin",
            func.lower(func.replace(func.btrim(name), "_", " ")),
            unique=True,
            postgresql_where=text("lower(replace(btrim(name), '_', ' ')) = 'super admin'"),
        ),
        Index("uq_roles_scope_normalized_name", organization_id, func.lower(func.btrim(name)),
              unique=True, postgresql_nulls_not_distinct=True),
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    key: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(150), nullable=False)

    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("lower(btrim(key)) <> 'all'", name="ck_permissions_no_wildcard"),
        Index("uq_permissions_normalized_key", func.lower(func.btrim(key)), unique=True),
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (Index("uq_role_permissions_pair", "role_id", "permission_id", unique=True),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    role_id: Mapped[str] = mapped_column(
        String, ForeignKey("roles.id", ondelete="CASCADE"), index=True
    )
    permission_id: Mapped[str] = mapped_column(
        String, ForeignKey("permissions.id", ondelete="CASCADE"), index=True
    )


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        Index("uq_user_roles_pair", "user_id", "role_id", unique=True),
        Index("uq_user_roles_user", "user_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role_id: Mapped[str] = mapped_column(
        String, ForeignKey("roles.id", ondelete="RESTRICT"), index=True
    )
