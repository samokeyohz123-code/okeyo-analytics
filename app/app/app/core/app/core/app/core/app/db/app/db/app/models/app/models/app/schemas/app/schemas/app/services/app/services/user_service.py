from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from app.models.models import User, UserRole
from app.core.security import hash_password
from app.schemas.schemas import UserCreate, UserUpdate
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> Optional[User]:
        r = await self.db.execute(select(User).where(User.id == user_id))
        return r.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        r = await self.db.execute(select(User).where(User.username == username.lower()))
        return r.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        r = await self.db.execute(select(User).where(User.email == email.lower()))
        return r.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 50, search: str = None):
        q = select(User)
        if search:
            q = q.where(
                User.full_name.ilike(f"%{search}%") |
                User.username.ilike(f"%{search}%") |
                User.email.ilike(f"%{search}%")
            )
        q = q.offset(skip).limit(limit).order_by(User.created_at.desc())
        r = await self.db.execute(q)
        users = r.scalars().all()
        count_r = await self.db.execute(select(func.count(User.id)))
        total = count_r.scalar()
        return users, total

    async def create(self, data: UserCreate, created_by: int = None) -> User:
        existing = await self.get_by_username(data.username)
        if existing:
            raise ValueError(f"Username '{data.username}' already exists")
        existing_email = await self.get_by_email(data.email)
        if existing_email:
            raise ValueError(f"Email '{data.email}' already registered")
        user = User(
            username=data.username.lower(),
            email=data.email.lower(),
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
            role=data.role,
            branch=data.branch,
            phone=data.phone,
            is_active=True,
            is_verified=True,
            created_by=created_by,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        logger.info(f"Created user: {user.username} ({user.role})")
        return user

    async def update(self, user_id: int, data: UserUpdate) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if not user:
            return None
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(user, field, value)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def update_password(self, user_id: int, new_password: str) -> bool:
        user = await self.get_by_id(user_id)
        if not user:
            return False
        user.hashed_password = hash_password(new_password)
        user.failed_logins = 0
        user.locked_until = None
        await self.db.flush()
        return True

    async def update_last_login(self, user_id: int, ip: str = None):
        await self.db.execute(
            update(User).where(User.id == user_id)
            .values(last_login=datetime.utcnow(), failed_logins=0, locked_until=None)
        )

    async def increment_failed_login(self, user_id: int):
        user = await self.get_by_id(user_id)
        if user:
            user.failed_logins = (user.failed_logins or 0) + 1
            if user.failed_logins >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=30)
                logger.warning(f"Account locked: {user.username}")
            await self.db.flush()

    async def disable(self, user_id: int) -> bool:
        user = await self.get_by_id(user_id)
        if not user:
            return False
        user.is_active = False
        await self.db.flush()
        return True

    async def enable(self, user_id: int) -> bool:
        user = await self.get_by_id(user_id)
        if not user:
            return False
        user.is_active = True
        user.failed_logins = 0
        user.locked_until = None
        await self.db.flush()
        return True
