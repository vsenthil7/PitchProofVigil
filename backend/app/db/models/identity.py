"""Identity & tenancy tables: tenants, users, API keys."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from app.db.models._base import JSONType, Role, utcnow, uuid_str


class Tenant(SQLModel, table=True):
    __tablename__ = "tenants"

    id: str = Field(default_factory=uuid_str, primary_key=True)
    name: str = Field(index=True)
    slug: str = Field(sa_column_kwargs={"unique": True})
    created_at: datetime = Field(default_factory=utcnow)
    is_active: bool = Field(default=True)


class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_user_email"),)

    id: str = Field(default_factory=uuid_str, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    email: str = Field(index=True)
    hashed_password: str
    role: Role = Field(sa_column=Column(SAEnum(Role)))
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)


class APIKey(SQLModel, table=True):
    __tablename__ = "api_keys"

    id: str = Field(default_factory=uuid_str, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str
    prefix: str = Field(index=True)
    hashed_secret: str
    role: Role = Field(sa_column=Column(SAEnum(Role)))
    created_at: datetime = Field(default_factory=utcnow)
    last_used_at: datetime | None = Field(default=None)
    revoked: bool = Field(default=False)


class TenantMembership(SQLModel, table=True):
    """A user's access to a tenant other than (or including) their home tenant.

    The ``users`` row still carries a user's *home* tenant and role — that's
    unchanged. Memberships are additive: they let one identity operate across
    tenants (e.g. a platform owner, or a consultant with access to two orgs),
    each with its own role in that tenant. A user's effective set of tenants is
    their home tenant ∪ their memberships. The pair (user_id, tenant_id) is
    unique so a user has at most one role per tenant.
    """

    __tablename__ = "tenant_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "tenant_id", name="uq_membership_user_tenant"),
    )

    id: str = Field(default_factory=uuid_str, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    role: Role = Field(sa_column=Column(SAEnum(Role)))
    created_at: datetime = Field(default_factory=utcnow)


class SSOConfigRow(SQLModel, table=True):
    """Per-tenant SAML 2.0 Identity Provider configuration."""

    __tablename__ = "sso_configs"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_sso_tenant"),)

    id: str = Field(default_factory=uuid_str, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True, unique=True)
    # IdP metadata (x509 cert stored encrypted via FieldCipher at the service layer)
    idp_entity_id: str
    idp_sso_url: str
    idp_x509_cert: str  # PEM-encoded; encrypted at rest
    sp_entity_id: str = Field(default="")  # SP metadata entityID for this tenant
    name_id_format: str = Field(
        default="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
    )
    attribute_mapping: dict = Field(
        default_factory=lambda: {"email": "urn:oid:1.2.840.113549.1.9.1"},
        sa_column=Column(JSONType),
    )
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
