from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.models.models import AuditLog
from typing import Optional
from fastapi import Request


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        username: str,
        action: str,
        resource: str = None,
        resource_id: int = None,
        details: str = None,
        ip_address: str = None,
        user_agent: str = None,
        user_id: int = None,
        success: bool = True,
        request: Request = None,
    ):
        if request:
            ip_address = ip_address or self._get_ip(request)
            user_agent = user_agent or request.headers.get("user-agent", "")[:500]

        entry = AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            resource=resource,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def get_all(self, skip: int = 0, limit: int = 100,
                      username: str = None, action: str = None):
        q = select(AuditLog).order_by(desc(AuditLog.created_at))
        if username:
            q = q.where(AuditLog.username.ilike(f"%{username}%"))
        if action:
            q = q.where(AuditLog.action.ilike(f"%{action}%"))
        q = q.offset(skip).limit(limit)
        r = await self.db.execute(q)
        items = r.scalars().all()
        count_r = await self.db.execute(select(func.count(AuditLog.id)))
        total = count_r.scalar()
        return items, total

    def _get_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"
