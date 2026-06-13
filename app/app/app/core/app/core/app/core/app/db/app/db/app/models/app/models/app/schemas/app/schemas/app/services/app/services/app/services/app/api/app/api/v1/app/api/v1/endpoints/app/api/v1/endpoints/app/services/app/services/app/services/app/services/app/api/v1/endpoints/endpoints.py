from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Optional
import io
from datetime import datetime

from app.db.session import get_db
from app.models.models import User, Customer, Statement, Analysis, Transaction, RiskRating
from app.schemas.schemas import *
from app.services.user_service import UserService
from app.services.audit_service import AuditService
from app.services.statement_service import StatementService
from app.services.analysis_service import AnalysisService
from app.core.security import get_current_active_user, require_admin, require_analyst
from app.core.config import settings


# ── USERS ─────────────────────────────────────────────────────
users_router = APIRouter(prefix="/users", tags=["Users"])

@users_router.get("", response_model=UserListResponse)
async def list_users(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100), search: Optional[str] = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
    svc = UserService(db)
    skip = (page - 1) * per_page
    users, total = await svc.get_all(skip=skip, limit=per_page, search=search)
    return UserListResponse(total=total, items=[UserResponse.model_validate(u) for u in users])

@users_router.post("", response_model=UserResponse, status_code=201)
async def create_user(data: UserCreate, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
    svc = UserService(db)
    try:
        user = await svc.create(data, created_by=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    await AuditService(db).log(username=current_user.username, action="USER_CREATED", resource="user", resource_id=user.id, request=request, user_id=current_user.id)
    await db.commit()
    return UserResponse.model_validate(user)

@users_router.put("/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, data: UserUpdate, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
    user = await UserService(db).update(user_id, data)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await AuditService(db).log(username=current_user.username, action="USER_UPDATED", resource="user", resource_id=user_id, request=request, user_id=current_user.id)
    await db.commit()
    return UserResponse.model_validate(user)

@users_router.post("/{user_id}/disable", response_model=SuccessResponse)
async def disable_user(user_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot disable your own account")
    ok = await UserService(db).disable(user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    await AuditService(db).log(username=current_user.username, action="USER_DISABLED", resource="user", resource_id=user_id, request=request, user_id=current_user.id)
    await db.commit()
    return SuccessResponse(message="User disabled successfully")

@users_router.post("/{user_id}/enable", response_model=SuccessResponse)
async def enable_user(user_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
    ok = await UserService(db).enable(user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    await AuditService(db).log(username=current_user.username, action="USER_ENABLED", resource="user", resource_id=user_id, request=request, user_id=current_user.id)
    await db.commit()
    return SuccessResponse(message="User enabled successfully")

@users_router.post("/{user_id}/reset-password", response_model=SuccessResponse)
async def reset_password(user_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
    import secrets, string
    chars = string.ascii_letters + string.digits + "!@#$"
    new_pwd = "".join(secrets.choice(chars) for _ in range(12))
    ok = await UserService(db).update_password(user_id, new_pwd)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    await AuditService(db).log(username=current_user.username, action="PASSWORD_RESET", resource="user", resource_id=user_id, request=request, user_id=current_user.id)
    await db.commit()
    return SuccessResponse(message="Password reset successfully", data={"temp_password": new_pwd})


# ── CUSTOMERS ─────────────────────────────────────────────────
customers_router = APIRouter(prefix="/customers", tags=["Customers"])

@customers_router.get("", response_model=CustomerListResponse)
async def list_customers(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100), search: Optional[str] = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    from sqlalchemy import or_
    q = select(Customer)
    if search:
        q = q.where(or_(Customer.full_name.ilike(f"%{search}%"), Customer.account_number.ilike(f"%{search}%"), Customer.bank_name.ilike(f"%{search}%")))
    skip = (page - 1) * per_page
    q = q.offset(skip).limit(per_page).order_by(Customer.created_at.desc())
    r = await db.execute(q)
    items = r.scalars().all()
    count_r = await db.execute(select(func.count(Customer.id)))
    total = count_r.scalar()
    return CustomerListResponse(total=total, items=[CustomerResponse.model_validate(c) for c in items])

@customers_router.post("", response_model=CustomerResponse, status_code=201)
async def create_customer(data: CustomerCreate, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_analyst)):
    customer = Customer(**data.model_dump(), created_by=current_user.id)
    db.add(customer)
    await db.flush()
    await db.refresh(customer)
    await AuditService(db).log(username=current_user.username, action="CUSTOMER_CREATED", resource="customer", resource_id=customer.id, details=f"Created: {customer.full_name}", request=request, user_id=current_user.id)
    await db.commit()
    return CustomerResponse.model_validate(customer)

@customers_router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(customer_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    r = await db.execute(select(Customer).where(Customer.id == customer_id))
    c = r.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return CustomerResponse.model_validate(c)

@customers_router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(customer_id: int, data: CustomerUpdate, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_analyst)):
    r = await db.execute(select(Customer).where(Customer.id == customer_id))
    c = r.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(c, field, value)
    await db.flush()
    await AuditService(db).log(username=current_user.username, action="CUSTOMER_UPDATED", resource="customer", resource_id=customer_id, request=request, user_id=current_user.id)
    await db.commit()
    return CustomerResponse.model_validate(c)

@customers_router.delete("/{customer_id}", response_model=SuccessResponse)
async def delete_customer(customer_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
    r = await db.execute(select(Customer).where(Customer.id == customer_id))
    c = r.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    await db.delete(c)
    await AuditService(db).log(username=current_user.username, action="CUSTOMER_DELETED", resource="customer", resource_id=customer_id, request=request, user_id=current_user.id)
    await db.commit()
    return SuccessResponse(message="Customer deleted")


# ── STATEMENTS ────────────────────────────────────────────────
statements_router = APIRouter(prefix="/statements", tags=["Statements"])

@statements_router.post("/upload", response_model=StatementResponse, status_code=201)
async def upload_statement(request: Request, background_tasks: BackgroundTasks, customer_id: int = Form(...), password: Optional[str] = Form(None), file: UploadFile = File(...), db: AsyncSession = Depends(get_db), current_user: User = Depends(require_analyst)):
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' not supported.")
    content = await file.read()
    if len(content) / (1024 * 1024) > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(status_code=413, detail=f"File too large. Max: {settings.MAX_UPLOAD_SIZE_MB}MB")
    r = await db.execute(select(Customer).where(Customer.id == customer_id))
    if not r.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Customer not found")
    svc = StatementService(db)
    stmt = await svc.upload(customer_id=customer_id, filename=file.filename, file_bytes=content, file_type=ext, uploaded_by=current_user.id, password=password)
    await AuditService(db).log(username=current_user.username, action="STATEMENT_UPLOADED", resource="statement", resource_id=stmt.id, details=f"File: {file.filename}", request=request, user_id=current_user.id)
    await db.commit()
    stmt_id = stmt.id
    background_tasks.add_task(_process_bg, stmt_id, password)
    return StatementResponse.model_validate(stmt)

async def _process_bg(statement_id: int, password: Optional[str]):
    from app.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            await StatementService(db).process(statement_id, password)
            await db.commit()
        except Exception as e:
            await db.rollback()
            from loguru import logger
            logger.error(f"Background processing failed for statement {statement_id}: {e}")

@statements_router.get("/{statement_id}", response_model=StatementResponse)
async def get_statement(statement_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    stmt = await StatementService(db).get_by_id(statement_id)
    if not stmt:
        raise HTTPException(status_code=404, detail="Statement not found")
    return StatementResponse.model_validate(stmt)

@statements_router.get("/{statement_id}/transactions", response_model=TransactionListResponse)
async def get_transactions(statement_id: int, page: int = Query(1, ge=1), per_page: int = Query(100, ge=1, le=1000), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    svc = StatementService(db)
    stmt = await svc.get_by_id(statement_id)
    if not stmt:
        raise HTTPException(status_code=404, detail="Statement not found")
    items, total = await svc.get_transactions(statement_id, skip=(page-1)*per_page, limit=per_page)
    return TransactionListResponse(total=total, statement=StatementResponse.model_validate(stmt), items=[TransactionResponse.model_validate(t) for t in items])

@statements_router.post("/{statement_id}/process", response_model=StatementResponse)
async def reprocess_statement(statement_id: int, request: Request, password: Optional[str] = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_analyst)):
    try:
        stmt = await StatementService(db).process(statement_id, password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await AuditService(db).log(username=current_user.username, action="STATEMENT_REPROCESSED", resource="statement", resource_id=statement_id, request=request, user_id=current_user.id)
    await db.commit()
    return StatementResponse.model_validate(stmt)

@statements_router.delete("/{statement_id}", response_model=SuccessResponse)
async def delete_statement(statement_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
    ok = await StatementService(db).delete(statement_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Statement not found")
    await AuditService(db).log(username=current_user.username, action="STATEMENT_DELETED", resource="statement", resource_id=statement_id, request=request, user_id=current_user.id)
    await db.commit()
    return SuccessResponse(message="Statement deleted")


# ── ANALYSIS ──────────────────────────────────────────────────
analysis_router = APIRouter(prefix="/analysis", tags=["Analysis"])

def _build_analysis_response(a: Analysis) -> AnalysisResponse:
    monthly = [MonthlyDataItem(**m) for m in (a.monthly_data or [])]
    concentration = [ConcentrationItem(**c) for c in (a.concentration_data or [])]
    trends = [TrendItem(**t) for t in (a.trend_data or [])]
    return AnalysisResponse(
        id=a.id, statement_id=a.statement_id,
        period_start=a.period_start, period_end=a.period_end,
        period_months=a.period_months, period_days=a.period_days,
        total_credits=a.total_credits, total_debits=a.total_debits, net_flow=a.net_flow,
        avg_monthly_credits=a.avg_monthly_credits, avg_monthly_debits=a.avg_monthly_debits,
        avg_balance=a.avg_balance, highest_balance=a.highest_balance, lowest_balance=a.lowest_balance,
        highest_single_credit=a.highest_single_credit, highest_single_debit=a.highest_single_debit,
        highest_credit_date=a.highest_credit_date, highest_credit_desc=a.highest_credit_desc,
        highest_debit_date=a.highest_debit_date, highest_debit_desc=a.highest_debit_desc,
        negative_balance_count=a.negative_balance_count, negative_balance_days=a.negative_balance_days,
        lowest_negative_balance=a.lowest_negative_balance, active_months=a.active_months,
        risk_rating=a.risk_rating.value if hasattr(a.risk_rating, "value") else str(a.risk_rating),
        risk_score=a.risk_score, risk_explanation=a.risk_explanation,
        ai_commentary=a.ai_commentary, ai_generated_at=a.ai_generated_at,
        monthly_data=monthly, concentration_data=concentration, trend_data=trends,
        created_at=a.created_at,
    )

@analysis_router.post("/run/{statement_id}", response_model=AnalysisResponse)
async def run_analysis(statement_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_analyst)):
    stmt = await StatementService(db).get_by_id(statement_id)
    if not stmt:
        raise HTTPException(status_code=404, detail="Statement not found")
    if stmt.status.value != "completed":
        raise HTTPException(status_code=400, detail=f"Statement not ready (status: {stmt.status.value})")
    try:
        analysis = await AnalysisService(db).run_analysis(statement_id, analyst_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await AuditService(db).log(username=current_user.username, action="ANALYSIS_RUN", resource="statement", resource_id=statement_id, details=f"Risk: {analysis.risk_rating}", request=request, user_id=current_user.id)
    await db.commit()
    return _build_analysis_response(analysis)

@analysis_router.get("/{statement_id}", response_model=AnalysisResponse)
async def get_analysis(statement_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    analysis = await AnalysisService(db).get_by_statement(statement_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found. Run analysis first.")
    return _build_analysis_response(analysis)

@analysis_router.post("/commentary/{statement_id}", response_model=SuccessResponse)
async def generate_commentary(statement_id: int, request: Request, force: bool = Query(False), db: AsyncSession = Depends(get_db), current_user: User = Depends(require_analyst)):
    try:
        commentary = await AnalysisService(db).generate_ai_commentary(statement_id, force=force)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await AuditService(db).log(username=current_user.username, action="AI_COMMENTARY_GENERATED", resource="statement", resource_id=statement_id, request=request, user_id=current_user.id)
    await db.commit()
    return SuccessResponse(message="Commentary generated", data={"commentary": commentary})


# ── REPORTS ───────────────────────────────────────────────────
reports_router = APIRouter(prefix="/reports", tags=["Reports"])

async def _get_report_data(statement_id: int, db: AsyncSession):
    analysis = await AnalysisService(db).get_by_statement(statement_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found. Run analysis first.")
    stmt = await StatementService(db).get_by_id(statement_id)
    r = await db.execute(select(Customer).where(Customer.id == stmt.customer_id))
    customer = r.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return analysis, stmt, customer

@reports_router.get("/pdf/{statement_id}")
async def download_pdf(statement_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_analyst)):
    analysis, statement, customer = await _get_report_data(statement_id, db)
    from app.services.pdf_report import PDFReportGenerator
    try:
        pdf_bytes = PDFReportGenerator(analysis, statement, customer, current_user.full_name).generate()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")
    filename = f"OKEYO_{customer.full_name.replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    await AuditService(db).log(username=current_user.username, action="REPORT_PDF_DOWNLOADED", resource="statement", resource_id=statement_id, request=request, user_id=current_user.id)
    await db.commit()
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})

@reports_router.get("/excel/{statement_id}")
async def download_excel(statement_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_analyst)):
    analysis, statement, customer = await _get_report_data(statement_id, db)
    svc = StatementService(db)
    txns, _ = await svc.get_transactions(statement_id, limit=100000)
    from app.services.excel_report import ExcelReportGenerator
    try:
        excel_bytes = ExcelReportGenerator(analysis, statement, customer, txns, current_user.full_name).generate()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Excel generation failed: {e}")
    filename = f"OKEYO_{customer.full_name.replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    await AuditService(db).log(username=current_user.username, action="REPORT_EXCEL_DOWNLOADED", resource="statement", resource_id=statement_id, request=request, user_id=current_user.id)
    await db.commit()
    return StreamingResponse(io.BytesIO(excel_bytes), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ── AUDIT LOGS ────────────────────────────────────────────────
audit_router = APIRouter(prefix="/audit", tags=["Audit"])

@audit_router.get("", response_model=AuditLogListResponse)
async def get_audit_logs(page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=200), username: Optional[str] = None, action: Optional[str] = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
    svc = AuditService(db)
    items, total = await svc.get_all(skip=(page-1)*per_page, limit=per_page, username=username, action=action)
    return AuditLogListResponse(total=total, items=[AuditLogResponse.model_validate(i) for i in items])


# ── DASHBOARD ─────────────────────────────────────────────────
dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@dashboard_router.get("", response_model=DashboardStats)
async def get_dashboard(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    customers_count  = (await db.execute(select(func.count(Customer.id)))).scalar()
    statements_count = (await db.execute(select(func.count(Statement.id)))).scalar()
    analyses_count   = (await db.execute(select(func.count(Analysis.id)))).scalar()
    low_r  = (await db.execute(select(func.count(Analysis.id)).where(Analysis.risk_rating == RiskRating.low))).scalar()
    mod_r  = (await db.execute(select(func.count(Analysis.id)).where(Analysis.risk_rating == RiskRating.moderate))).scalar()
    high_r = (await db.execute(select(func.count(Analysis.id)).where(Analysis.risk_rating == RiskRating.high))).scalar()
    recent_uploads_r = await db.execute(select(Statement, Customer).join(Customer, Statement.customer_id == Customer.id).order_by(desc(Statement.uploaded_at)).limit(5))
    recent_uploads = [{"id": s.id, "customer": c.full_name, "file": s.original_name, "status": s.status.value, "uploaded_at": s.uploaded_at.isoformat()} for s, c in recent_uploads_r.all()]
    recent_analyses_r = await db.execute(select(Analysis, Statement, Customer).join(Statement, Analysis.statement_id == Statement.id).join(Customer, Statement.customer_id == Customer.id).order_by(desc(Analysis.created_at)).limit(5))
    recent_analyses = [{"id": a.id, "customer": c.full_name, "risk": a.risk_rating.value if hasattr(a.risk_rating, "value") else str(a.risk_rating), "score": a.risk_score, "credits": a.total_credits, "created_at": a.created_at.isoformat()} for a, s, c in recent_analyses_r.all()]
    return DashboardStats(total_customers=customers_count, total_statements=statements_count, total_analyses=analyses_count, low_risk_count=low_r, moderate_risk_count=mod_r, high_risk_count=high_r, recent_uploads=recent_uploads, recent_analyses=recent_analyses)
