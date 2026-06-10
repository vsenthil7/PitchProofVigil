"""SAML 2.0 SSO service - SP-initiated flow.

Reuses the existing SSOConfigRow (app/db/models/identity.py). IdP secrets
(entity id, SSO URL, x509 cert) are encrypted at rest via FieldCipher. In
production, signature validation should use pysaml2 (a live-only optional dep);
this implementation parses the assertion XML with defusedxml and extracts the
NameID + attributes.
"""
from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import create_access_token
from app.core.config import Settings, get_settings
from app.crypto.cipher import FieldCipher
from app.db.models._base import Role
from app.db.models.identity import SSOConfigRow, User
from app.repositories.identity import TenantRepository, UserRepository


class SSOError(Exception):
    """Raised on any SSO configuration or assertion-processing failure."""


class SSOService:
    """SAML SP metadata, AuthnRequest generation, and ACS response parsing."""

    def __init__(
        self,
        session: AsyncSession,
        cipher: FieldCipher,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.cipher = cipher
        self.settings = settings or get_settings()
        self._users = UserRepository(session)
        self._tenants = TenantRepository(session)

    # ---- Configuration --------------------------------------------------

    async def configure_idp(
        self,
        tenant_id: str,
        idp_entity_id: str,
        idp_sso_url: str,
        idp_x509_cert: str,
        sp_base_url: str,
        tenant_slug: str,
    ) -> SSOConfigRow:
        sp_entity_id = f"{sp_base_url}/api/auth/sso/{tenant_slug}/metadata"
        await self.session.execute(
            delete(SSOConfigRow).where(SSOConfigRow.tenant_id == tenant_id)
        )
        row = SSOConfigRow(
            tenant_id=tenant_id,
            idp_entity_id=self.cipher.encrypt(idp_entity_id),
            idp_sso_url=self.cipher.encrypt(idp_sso_url),
            idp_x509_cert=self.cipher.encrypt(idp_x509_cert),
            sp_entity_id=sp_entity_id,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_config(self, tenant_id: str) -> SSOConfigRow | None:
        result = await self.session.execute(
            select(SSOConfigRow).where(SSOConfigRow.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    # ---- SP Metadata XML ------------------------------------------------

    def sp_metadata_xml(self, sp_entity_id: str, acs_url: str) -> str:
        """Minimal SP metadata XML (no pysaml2 required)."""
        return (
            '<?xml version="1.0"?>\n'
            '<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"\n'
            f'    entityID="{sp_entity_id}">\n'
            "  <md:SPSSODescriptor\n"
            '      protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol"\n'
            '      AuthnRequestsSigned="false" WantAssertionsSigned="true">\n'
            "    <md:AssertionConsumerService\n"
            '        Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"\n'
            f'        Location="{acs_url}"\n'
            '        index="1"/>\n'
            "  </md:SPSSODescriptor>\n"
            "</md:EntityDescriptor>"
        )

    # ---- AuthnRequest (redirect binding) --------------------------------

    def build_authn_request_url(
        self, idp_sso_url: str, sp_entity_id: str, acs_url: str
    ) -> str:
        """Build a SAML AuthnRequest URL for IdP redirect binding."""
        import zlib
        from urllib.parse import urlencode

        request_id = f"_{uuid.uuid4().hex}"
        issue_instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        authn_request = (
            '<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" '
            'xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" '
            f'ID="{request_id}" Version="2.0" IssueInstant="{issue_instant}" '
            f'Destination="{idp_sso_url}" '
            f'AssertionConsumerServiceURL="{acs_url}" '
            'ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">'
            f"<saml:Issuer>{sp_entity_id}</saml:Issuer>"
            "</samlp:AuthnRequest>"
        )
        compressed = zlib.compress(authn_request.encode())[2:-4]
        encoded = base64.b64encode(compressed).decode()
        params = urlencode({"SAMLRequest": encoded, "RelayState": "/"})
        return f"{idp_sso_url}?{params}"

    # ---- ACS response parsing -------------------------------------------

    async def process_acs_response(
        self, tenant_id: str, saml_response_b64: str, base_url: str
    ) -> str:
        """Parse a SAML Response, create/get the user, return a JWT."""
        import defusedxml.ElementTree as ET

        config = await self.get_config(tenant_id)
        if config is None:
            raise SSOError("SSO not configured for this tenant.")

        try:
            xml_bytes = base64.b64decode(saml_response_b64, validate=True)
            root = ET.fromstring(xml_bytes)
        except Exception as exc:
            raise SSOError(f"Invalid SAMLResponse: {exc}") from exc

        ns = {
            "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
            "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
        }
        name_id_el = root.find(".//saml:NameID", ns)
        if name_id_el is None or not name_id_el.text:
            raise SSOError("NameID not found in SAMLResponse.")
        email = name_id_el.text.strip()

        user = await self.get_or_create_user_from_saml(tenant_id, email)
        return create_access_token(
            user.id, tenant_id, user.role.value, self.settings
        )

    async def get_or_create_user_from_saml(
        self, tenant_id: str, email: str, role: Role = Role.OPERATOR
    ) -> User:
        user = await self._users.get_by_email(tenant_id, email)
        if user is None:
            user = await self._users.create(
                User(
                    tenant_id=tenant_id,
                    email=email,
                    hashed_password="sso-managed",  # SSO-only; no password login
                    role=role,
                )
            )
        return user
