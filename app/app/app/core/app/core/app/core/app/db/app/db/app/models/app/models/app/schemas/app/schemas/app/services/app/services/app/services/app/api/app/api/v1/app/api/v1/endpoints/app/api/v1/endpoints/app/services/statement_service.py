from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from app.models.models import Statement, Transaction, Customer, StatementStatus, FileType
from app.services.parser import StatementParser
from app.core.security import compute_file_hash, secure_filename
from app.core.config import settings
from datetime import datetime
from typing import Optional
from pathlib import Path
import aiofiles
import os
from loguru import logger


class StatementService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upload(self, customer_id: int, filename: str, file_bytes: bytes, file_type: str, uploaded_by: int, password: Optional[str] = None) -> Statement:
        upload_dir = Path(settings.UPLOAD_DIR) / str(customer_id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        safe_name = secure_filename(filename)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        stored_name = f"{ts}_{safe_name}"
        file_path = upload_dir / stored_name
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_bytes)
        stmt = Statement(
            customer_id=customer_id,
            uploaded_by=uploaded_by,
            original_name=filename,
            file_path=str(file_path),
            file_type=file_type.lower().strip("."),
            file_size_kb=max(1, len(file_bytes) // 1024),
            file_hash=compute_file_hash(file_bytes),
            is_password_protected=bool(password),
            status=StatementStatus.pending,
        )
        self.db.add(stmt)
        await self.db.flush()
        await self.db.refresh(stmt)
        logger.info(f"Statement uploaded: {filename} for customer {customer_id}")
        return stmt

    async def process(self, statement_id: int, password: Optional[str] = None) -> Statement:
        stmt = await self.get_by_id(statement_id)
        if not stmt:
            raise ValueError("Statement not found")
        stmt.status = StatementStatus.processing
        await self.db.flush()
        try:
            async with aiofiles.open(stmt.file_path, "rb") as f:
                file_bytes = await f.read()
            logger.info(f"Parsing {stmt.file_type} statement: {stmt.original_name}")
            raw_transactions = StatementParser.parse(file_bytes, stmt.file_type, password)
            if not raw_transactions:
                raise ValueError("No transactions could be extracted from this file.")
            logger.info(f"Extracted {len(raw_transactions)} transactions")
            txn_objects = [
                Transaction(
                    statement_id=stmt.id,
                    txn_date=t.txn_date,
                    description=t.description,
                    credit=round(t.credit, 2),
                    debit=round(t.debit, 2),
                    balance=round(t.balance, 2) if t.balance is not None else None,
                    reference=t.reference,
                    raw_row=t.raw_row,
                )
                for t in raw_transactions
            ]
            self.db.add_all(txn_objects)
            await self.db.flush()
            dates = [t.txn_date for t in raw_transactions]
            stmt.transaction_count = len(raw_transactions)
            stmt.date_from = min(dates)
            stmt.date_to   = max(dates)
            stmt.status    = StatementStatus.completed
            stmt.processed_at = datetime.utcnow()
            await self.db.flush()
            await self.db.refresh(stmt)
            logger.info(f"Statement {stmt.id} processed successfully")
            return stmt
        except Exception as e:
            stmt.status = StatementStatus.failed
            stmt.error_message = str(e)[:500]
            await self.db.flush()
            logger.error(f"Statement processing failed: {e}")
            raise

    async def get_by_id(self, statement_id: int) -> Optional[Statement]:
        r = await self.db.execute(select(Statement).options(selectinload(Statement.customer)).where(Statement.id == statement_id))
        return r.scalar_one_or_none()

    async def get_transactions(self, statement_id: int, skip: int = 0, limit: int = 500):
        r = await self.db.execute(select(Transaction).where(Transaction.statement_id == statement_id).order_by(Transaction.txn_date).offset(skip).limit(limit))
        items = r.scalars().all()
        count_r = await self.db.execute(select(func.count(Transaction.id)).where(Transaction.statement_id == statement_id))
        total = count_r.scalar()
        return items, total

    async def delete(self, statement_id: int) -> bool:
        stmt = await self.get_by_id(statement_id)
        if not stmt:
            return False
        try:
            if os.path.exists(stmt.file_path):
                os.remove(stmt.file_path)
        except Exception:
            pass
        await self.db.delete(stmt)
        await self.db.flush()
        return True
