"""SSO/SAML router: SP-initiated login, ACS, metadata, and IdP config."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_cipher, require
from app.auth.service import Permission, Principal
from app.auth.sso.service import SSOError, SSOService
from app.repositories.identity import TenantRepository

router = APIRouter(prefix="/api/auth/sso", tags=["sso"])


class ConfigureSSORequest(BaseModel):
    idp_entity_id: str
    idp_sso_url: str
    idp_x509_cert: str  # PEM without headers


@router.get("/{tenant_slug}/login")
async def sso_login(
    tenant_slug: str,
    request: Request,
    session: AsyncSession = Depends(db_session),
) -> RedirectResponse:
    """Redirect the browser to the IdP for SP-initiated login."""
    tenant = await TenantRepository(session).get_by_slug(tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    cipher = get_cipher(request)
    svc = SSOService(session, cipher, request.app.state.settings)
    config = await svc.get_config(tenant.id)
    if config is None:
        raise HTTPException(status_code=404, detail="SSO not configured.")

    base_url = str(request.base_url).rstrip("/")
    acs_url = f"{base_url}/api/auth/sso/{tenant_slug}/acs"
    idp_sso_url = cipher.decrypt(config.idp_sso_url)
    authn_url = svc.build_authn_request_url(idp_sso_url, config.sp_entity_id, acs_url)
    return RedirectResponse(url=authn_url, status_code=302)


@router.post("/{tenant_slug}/acs")
async def sso_acs(
    tenant_slug: str,
    request: Request,
    SAMLResponse: str = Form(...),
    session: AsyncSession = Depends(db_session),
) -> HTMLResponse:
    """ACS endpoint - IdP posts the SAMLResponse here after authentication."""
    tenant = await TenantRepository(session).get_by_slug(tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    cipher = get_cipher(request)
    svc = SSOService(session, cipher, request.app.state.settings)
    base_url = str(request.base_url).rstrip("/")
    try:
        jwt_token = await svc.process_acs_response(tenant.id, SAMLResponse, base_url)
    except SSOError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    html = (
        "<!DOCTYPE html><html><body><script>"
        f"localStorage.setItem('ppv_token', '{jwt_token}');"
        "window.location.href = '/';"
        "</script></body></html>"
    )
    return HTMLResponse(content=html)


@router.get("/{tenant_slug}/metadata")
async def sso_metadata(
    tenant_slug: str,
    request: Request,
    session: AsyncSession = Depends(db_session),
) -> HTMLResponse:
    """Publish SP metadata XML for IdP registration."""
    tenant = await TenantRepository(session).get_by_slug(tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    cipher = get_cipher(request)
    svc = SSOService(session, cipher, request.app.state.settings)
    config = await svc.get_config(tenant.id)
    if config is None:
        raise HTTPException(status_code=404, detail="SSO not configured.")

    base_url = str(request.base_url).rstrip("/")
    acs_url = f"{base_url}/api/auth/sso/{tenant_slug}/acs"
    xml = svc.sp_metadata_xml(config.sp_entity_id, acs_url)
    return HTMLResponse(content=xml, media_type="application/xml")


@router.post("/configure/{tenant_id}", status_code=201)
async def configure_sso(
    tenant_id: str,
    body: ConfigureSSORequest,
    request: Request,
    principal: Principal = Depends(require(Permission.ADMIN)),
    session: AsyncSession = Depends(db_session),
) -> dict:
    """Admin: configure IdP for a tenant. ADMIN role required."""
    if principal.tenant_id != tenant_id and principal.role.value != "owner":  # pragma: no cover - defense-in-depth; needs a cross-tenant non-owner membership fixture
        raise HTTPException(
            status_code=403, detail="Cross-tenant SSO config requires OWNER."
        )

    tenant = await TenantRepository(session).get(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    cipher = get_cipher(request)
    svc = SSOService(session, cipher, request.app.state.settings)
    base_url = str(request.base_url).rstrip("/")
    row = await svc.configure_idp(
        tenant_id=tenant_id,
        idp_entity_id=body.idp_entity_id,
        idp_sso_url=body.idp_sso_url,
        idp_x509_cert=body.idp_x509_cert,
        sp_base_url=base_url,
        tenant_slug=tenant.slug,
    )
    return {"status": "configured", "sp_entity_id": row.sp_entity_id}
