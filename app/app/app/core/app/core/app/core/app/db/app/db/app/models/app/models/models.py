from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Enum, JSON, Index, UniqueConstraint
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func
import enum


class Base(DeclarativeBase):
    pass


class UserRole(str, enum.Enum):
    administrator        = "administrator"
    credit_analyst       = "credit_analyst"
    relationship_manager = "relationship_manager"
    branch_manager       = "branch_manager"
    read_only            = "read_only"

class RiskRating(str, enum.Enum):
    low      = "LOW"
    moderate = "MODERATE"
    high     = "HIGH"

class StatementStatus(str, enum.Enum):
    pending    = "pending"
    processing = "processing"
    completed  = "completed"
    failed     = "failed"

class FileType(str, enum.Enum):
    pdf  = "pdf"
    xlsx = "xlsx"
    xls  = "xls"
    csv  = "csv"


class User(Base):
    __tablename__ = "users"
    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String(50), unique=True, nullable=False, index=True)
    email           = Column(String(255), unique=True, nullable=False, index=True)
    full_name       = Column(String(150), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role            = Column(Enum(UserRole), default=UserRole.read_only, nullable=False)
    is_active       = Column(Boolean, default=True)
    is_verified     = Column(Boolean, default=False)
    branch          = Column(String(100), nullable=True)
    phone           = Column(String(20), nullable=True)
    last_login      = Column(DateTime(timezone=True), nullable=True)
    failed_logins   = Column(Integer, default=0)
    locked_until    = Column(DateTime(timezone=True), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())
    created_by      = Column(Integer, ForeignKey("users.id"), nullable=True)
    statements      = relationship("Statement", back_populates="uploaded_by_user", foreign_keys="Statement.uploaded_by")
    audit_logs      = relationship("AuditLog", back_populates="user")
    analyses        = relationship("Analysis", back_populates="analyst_user", foreign_keys="Analysis.analyst_id")


class Customer(Base):
    __tablename__ = "customers"
    id              = Column(Integer, primary_key=True, index=True)
    full_name       = Column(String(200), nullable=False, index=True)
    account_number  = Column(String(50), nullable=False)
    bank_name       = Column(String(100), nullable=False)
    id_number       = Column(String(50), nullable=True)
    phone           = Column(String(20), nullable=True)
    email           = Column(String(255), nullable=True)
    customer_type   = Column(String(50), default="Individual")
    notes           = Column(Text, nullable=True)
    created_by      = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())
    statements      = relationship("Statement", back_populates="customer")
    creator         = relationship("User", foreign_keys=[created_by])
    __table_args__  = (UniqueConstraint("account_number", "bank_name", name="uq_account_bank"),)


class Statement(Base):
    __tablename__ = "statements"
    id                    = Column(Integer, primary_key=True, index=True)
    customer_id           = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    uploaded_by           = Column(Integer, ForeignKey("users.id"), nullable=False)
    original_name         = Column(String(255), nullable=False)
    file_path             = Column(String(500), nullable=False)
    file_type             = Column(Enum(FileType), nullable=False)
    file_size_kb          = Column(Integer, nullable=False)
    file_hash             = Column(String(64), nullable=True)
    is_password_protected = Column(Boolean, default=False)
    status                = Column(Enum(StatementStatus), default=StatementStatus.pending)
    error_message         = Column(Text, nullable=True)
    page_count            = Column(Integer, nullable=True)
    transaction_count     = Column(Integer, nullable=True)
    date_from             = Column(DateTime, nullable=True)
    date_to               = Column(DateTime, nullable=True)
    uploaded_at           = Column(DateTime(timezone=True), server_default=func.now())
    processed_at          = Column(DateTime(timezone=True), nullable=True)
    customer              = relationship("Customer", back_populates="statements")
    uploaded_by_user      = relationship("User", back_populates="statements", foreign_keys=[uploaded_by])
    transactions          = relationship("Transaction", back_populates="statement", cascade="all, delete-orphan")
    analysis              = relationship("Analysis", back_populates="statement", uselist=False)


class Transaction(Base):
    __tablename__ = "transactions"
    id           = Column(Integer, primary_key=True, index=True)
    statement_id = Column(Integer, ForeignKey("statements.id"), nullable=False, index=True)
    txn_date     = Column(DateTime, nullable=False, index=True)
    description  = Column(Text, nullable=False)
    credit       = Column(Float, default=0.0)
    debit        = Column(Float, default=0.0)
    balance      = Column(Float, nullable=True)
    reference    = Column(String(100), nullable=True)
    raw_row      = Column(Integer, nullable=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    statement    = relationship("Statement", back_populates="transactions")
    __table_args__ = (Index("ix_txn_statement_date", "statement_id", "txn_date"),)


class Analysis(Base):
    __tablename__ = "analyses"
    id                       = Column(Integer, primary_key=True, index=True)
    statement_id             = Column(Integer, ForeignKey("statements.id"), nullable=False, unique=True)
    analyst_id               = Column(Integer, ForeignKey("users.id"), nullable=False)
    period_start             = Column(DateTime, nullable=True)
    period_end               = Column(DateTime, nullable=True)
    period_months            = Column(Integer, nullable=True)
    period_days              = Column(Integer, nullable=True)
    total_credits            = Column(Float, default=0.0)
    total_debits             = Column(Float, default=0.0)
    net_flow                 = Column(Float, default=0.0)
    avg_monthly_credits      = Column(Float, default=0.0)
    avg_monthly_debits       = Column(Float, default=0.0)
    avg_balance              = Column(Float, default=0.0)
    highest_balance          = Column(Float, default=0.0)
    lowest_balance           = Column(Float, default=0.0)
    highest_single_credit    = Column(Float, default=0.0)
    highest_single_debit     = Column(Float, default=0.0)
    highest_credit_date      = Column(DateTime, nullable=True)
    highest_credit_desc      = Column(Text, nullable=True)
    highest_debit_date       = Column(DateTime, nullable=True)
    highest_debit_desc       = Column(Text, nullable=True)
    negative_balance_count   = Column(Integer, default=0)
    negative_balance_days    = Column(Integer, default=0)
    lowest_negative_balance  = Column(Float, default=0.0)
    active_months            = Column(Integer, default=0)
    risk_rating              = Column(Enum(RiskRating), default=RiskRating.moderate)
    risk_score               = Column(Integer, default=50)
    risk_explanation         = Column(Text, nullable=True)
    ai_commentary            = Column(Text, nullable=True)
    ai_generated_at          = Column(DateTime(timezone=True), nullable=True)
    monthly_data             = Column(JSON, nullable=True)
    concentration_data       = Column(JSON, nullable=True)
    trend_data               = Column(JSON, nullable=True)
    turnover_score           = Column(Integer, default=0)
    conduct_score            = Column(Integer, default=0)
    growth_score             = Column(Integer, default=0)
    concentration_score      = Column(Integer, default=0)
    created_at               = Column(DateTime(timezone=True), server_default=func.now())
    updated_at               = Column(DateTime(timezone=True), onupdate=func.now())
    statement                = relationship("Statement", back_populates="analysis")
    analyst_user             = relationship("User", back_populates="analyses", foreign_keys=[analyst_id])


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=True)
    username    = Column(String(50), nullable=False)
    action      = Column(String(100), nullable=False, index=True)
    resource    = Column(String(100), nullable=True)
    resource_id = Column(Integer, nullable=True)
    details     = Column(Text, nullable=True)
    ip_address  = Column(String(45), nullable=True)
    user_agent  = Column(String(500), nullable=True)
    success     = Column(Boolean, default=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    user        = relationship("User", back_populates="audit_logs")
    __table_args__ = (Index("ix_audit_user_created", "user_id", "created_at"),)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked    = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user       = relationship("User")
