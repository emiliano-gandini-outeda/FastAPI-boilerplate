from typing import Any

from crudauth import Principal
from crudauth.exceptions import UnauthorizedException
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from ...modules.user.crud import crud_users
from ..dependencies import AsyncSessionDep, OAuth2FormDep
from ..logging import get_logger
from .dependencies import get_optional_principal
from .setup import auth as crud_auth

logger = get_logger()
router = APIRouter(tags=["Authentication"])


@router.post("/login")
async def login(request: Request, response: Response, form_data: OAuth2FormDep, db: AsyncSessionDep) -> dict[str, str]:
    user = await crud_auth.authenticate_password(db, form_data.username, form_data.password, request=request)
    session_id, csrf_token = await crud_auth.sessions.create_session(
        request, user_id=crud_auth.repo.user_id(user), metadata={"login_type": "password"}
    )
    crud_auth.sessions.set_session_cookies(response, session_id, csrf_token)
    return {"csrf_token": csrf_token}


@router.post("/logout")
async def logout(response: Response, principal: Principal = Depends(crud_auth.current_user())) -> dict[str, str]:
    session_id = principal.metadata.get("session_id")
    if session_id:
        await crud_auth.sessions.revoke(session_id, owner_id=principal.user_id)
    crud_auth.sessions.clear_session_cookies(response)
    return {"message": "Logged out successfully"}


router.include_router(crud_auth.oauth_router)


@router.post("/refresh-csrf", responses={401: {"description": "Not authenticated"}})
async def refresh_csrf_token(request: Request, response: Response) -> dict[str, str]:
    """Refresh the CSRF token without requiring a CSRF header."""
    sessions = crud_auth.sessions
    session_id = request.cookies.get(sessions.session_cookie_name)
    session = await sessions.validate_session(session_id) if session_id else None
    if session is None or session_id is None:
        raise UnauthorizedException("Not authenticated")

    ttl_seconds = sessions.timeout_seconds_for(session.metadata)
    csrf_token = await sessions.regenerate_csrf_token(
        user_id=session.user_id, session_id=session_id, expiration_seconds=ttl_seconds
    )
    sessions.set_csrf_cookie(response, csrf_token, max_age=ttl_seconds)
    return {"csrf_token": csrf_token}


@router.get("/check-auth")
async def check_auth(
    db: AsyncSessionDep,
    principal: Principal | None = Depends(get_optional_principal),
) -> dict[str, Any]:
    """Return authentication status and a small user summary."""
    if principal is None:
        return {"authenticated": False, "message": "Not authenticated"}

    try:
        user = await crud_users.get(db=db, id=principal.user_id, is_deleted=False)
        if not user:
            return {"authenticated": False, "message": "User not found"}

        session_id = principal.metadata.get("session_id")
        session = await crud_auth.sessions.validate_session(session_id) if session_id else None
        return {
            "authenticated": True,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "oauth_provider": user.get("oauth_provider"),
            },
            "session": {
                "created_at": session.created_at.isoformat() if session and session.created_at else None,
                "last_activity": session.last_activity.isoformat() if session and session.last_activity else None,
            },
        }
    except Exception as exc:
        logger.error(f"Error checking authentication: {exc}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error checking authentication status")
