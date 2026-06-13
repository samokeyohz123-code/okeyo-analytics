from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import hashlib

from app.db.session import get_db
from app.schemas.schemas import LoginRequest, TokenResponse, RefreshRequest, ChangePasswordRequest, SuccessResponse
from app.services.user_service import UserService
from app.services.audit_service import AuditService
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token, get_current_active_user, settings
from app.models.models import RefreshToken, User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    audit = AuditService(db)
    user_svc = UserService(db)
    user = await user_svc.get_by_username(data.username)
    if not user:
        await audit.log(username=data.username, action="LOGIN_FAILED", details="User not found", request=request, success=False)
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if user.locked_until and user.locked_until > datetime.utcnow():
        mins = int((user.locked_until - datetime.utcnow()).seconds / 60) + 1
        raise HTTPException(status_code=423, detail=f"Account locked. Try again in {mins} minutes.")
    if not verify_password(data.password, user.hashed_password):
        await user_svc.increment_failed_login(user.id)
        await audit.log(username=data.username, action="LOGIN_FAILED", details="Wrong password", request=request, success=False, user_id=user.id)
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled. Contact administrator.")
    expire = timedelta(days=7) if data.remember_me else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token  = create_access_token({"sub": user.username}, expires_delta=expire)
    refresh_token = create_refresh_token({"sub": user.username})
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    rt = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", "")[:500],
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(rt)
    await user_svc.update_last_login(user.id)
    await audit.log(username=user.username, action="LOGIN_SUCCESS", request=request, success=True, user_id=user.id)
    await db.commit()
    from app.schemas.schemas import UserResponse
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=int(expire.total_seconds()),
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    import time
    payload = decode_token(data.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    token_hash = hashlib.sha256(data.refresh_token.encode()).hexdigest()
    r = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash, RefreshToken.revoked == False, RefreshToken.expires_at > datetime.utcnow()))
    stored = r.scalar_one_or_none()
    if not stored:
        raise HTTPException(status_code=401, detail="Refresh token invalid or expired")
    user_svc = UserService(db)
    user = await user_svc.get_by_username(payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")
    stored.revoked = True
    new_access  = create_access_token({"sub": user.username})
    new_refresh = create_refresh_token({"sub": user.username})
    new_hash = hashlib.sha256(f"{new_refresh}{time.time_ns()}".encode()).hexdigest()
    db.add(RefreshToken(user_id=user.id, token_hash=new_hash, ip_address=request.client.host if request.client else None, expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)))
    await db.commit()
    from app.schemas.schemas import UserResponse
    return TokenResponse(access_token=new_access, refresh_token=new_refresh, expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, user=UserResponse.model_validate(user))


@router.post("/logout", response_model=SuccessResponse)
async def logout(data: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    from sqlalchemy import update
    token_hash = hashlib.sha256(data.refresh_token.encode()).hexdigest()
    await db.execute(update(RefreshToken).where(RefreshToken.token_hash == token_hash).values(revoked=True))
    await AuditService(db).log(username=current_user.username, action="LOGOUT", request=request, user_id=current_user.id)
    await db.commit()
    return SuccessResponse(message="Logged out successfully")


@router.post("/change-password", response_model=SuccessResponse)
async def change_password(data: ChangePasswordRequest, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    from app.core.security import verify_password, validate_password_strength
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    valid, msg = validate_password_strength(data.new_password)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)
    await UserService(db).update_password(current_user.id, data.new_password)
    await AuditService(db).log(username=current_user.username, action="PASSWORD_CHANGED", request=request, user_id=current_user.id)
    await db.commit()
    return SuccessResponse(message="Password changed successfully")


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_active_user)):
    from app.schemas.schemas import UserResponse
    return UserResponse.model_validate(current_user)
