from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum


class LoginRequest(BaseModel):
    username: str
    password: str
    remember_me: bool = False

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserResponse"

class RefreshRequest(BaseModel):
    refresh_token: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class UserRole(str, Enum):
    administrator        = "administrator"
    credit_analyst       = "credit_analyst"
    relationship_manager = "relationship_manager"
    branch_manager       = "branch_manager"
    read_only            = "read_only"

class UserCreate(BaseModel):
    username:  str
    email:     EmailStr
    full_name: str
    password:  str
    role:      UserRole = UserRole.read_only
    branch:    Optional[str] = None
    phone:     Optional[str] = None

    @field_validator("username")
    @classmethod
    def username_valid(cls, v):
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters")
        return v.lower().strip()

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email:     Optional[EmailStr] = None
    role:      Optional[UserRole] = None
    branch:    Optional[str] = None
    phone:     Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(BaseModel):
    id:         int
    username:   str
    email:      str
    full_name:  str
    role:       str
    is_active:  bool
    branch:     Optional[str] = None
    last_login: Optional[datetime] = None
    created_at: datetime
    model_config = {"from_attributes": True}

class UserListResponse(BaseModel):
    total: int
    items: List[UserResponse]

class CustomerCreate(BaseModel):
    full_name:      str
    account_number: str
    bank_name:      str
    id_number:      Optional[str] = None
    phone:          Optional[str] = None
    email:          Optional[EmailStr] = None
    customer_type:  str = "Individual"
    notes:          Optional[str] = None

class CustomerUpdate(BaseModel):
    full_name:     Optional[str] = None
    bank_name:     Optional[str] = None
    id_number:     Optional[str] = None
    phone:         Optional[str] = None
    email:         Optional[EmailStr] = None
    customer_type: Optional[str] = None
    notes:         Optional[str] = None

class CustomerResponse(BaseModel):
    id:             int
    full_name:      str
    account_number: str
    bank_name:      str
    id_number:      Optional[str] = None
    phone:          Optional[str] = None
    email:          Optional[str] = None
    customer_type:  str
    created_at:     datetime
    model_config = {"from_attributes": True}

class CustomerListResponse(BaseModel):
    total: int
    items: List[CustomerResponse]

class StatementResponse(BaseModel):
    id:                int
    customer_id:       int
    original_name:     str
    file_type:         str
    file_size_kb:      int
    status:            str
    page_count:        Optional[int] = None
    transaction_count: Optional[int] = None
    date_from:         Optional[datetime] = None
    date_to:           Optional[datetime] = None
    uploaded_at:       datetime
    processed_at:      Optional[datetime] = None
    error_message:     Optional[str] = None
    model_config = {"from_attributes": True}

class TransactionResponse(BaseModel):
    id:          int
    txn_date:    datetime
    description: str
    credit:      float
    debit:       float
    balance:     Optional[float] = None
    reference:   Optional[str] = None
    model_config = {"from_attributes": True}

class TransactionListResponse(BaseModel):
    total:     int
    statement: StatementResponse
    items:     List[TransactionResponse]

class MonthlyDataItem(BaseModel):
    month:     str
    year:      int
    month_num: int
    credits:   float
    debits:    float
    high_bal:  float
    low_bal:   float
    avg_bal:   float
    txn_count: int

class ConcentrationItem(BaseModel):
    source:    str
    amount:    float
    pct:       float
    txn_count: int

class TrendItem(BaseModel):
    month:      str
    credits:    float
    debits:     float
    mom_growth: Optional[float] = None
    direction:  str

class RiskResult(BaseModel):
    rating:              str
    score:               int
    explanation:         str
    turnover_score:      int
    conduct_score:       int
    growth_score:        int
    concentration_score: int

class AnalysisResponse(BaseModel):
    id:                      int
    statement_id:            int
    period_start:            Optional[datetime] = None
    period_end:              Optional[datetime] = None
    period_months:           Optional[int] = None
    period_days:             Optional[int] = None
    total_credits:           float
    total_debits:            float
    net_flow:                float
    avg_monthly_credits:     float
    avg_monthly_debits:      float
    avg_balance:             float
    highest_balance:         float
    lowest_balance:          float
    highest_single_credit:   float
    highest_single_debit:    float
    highest_credit_date:     Optional[datetime] = None
    highest_credit_desc:     Optional[str] = None
    highest_debit_date:      Optional[datetime] = None
    highest_debit_desc:      Optional[str] = None
    negative_balance_count:  int
    negative_balance_days:   int
    lowest_negative_balance: float
    active_months:           int
    risk_rating:             str
    risk_score:              int
    risk_explanation:        Optional[str] = None
    ai_commentary:           Optional[str] = None
    ai_generated_at:         Optional[datetime] = None
    monthly_data:            Optional[List[MonthlyDataItem]] = None
    concentration_data:      Optional[List[ConcentrationItem]] = None
    trend_data:              Optional[List[TrendItem]] = None
    created_at:              datetime
    model_config = {"from_attributes": True}

class AuditLogResponse(BaseModel):
    id:         int
    username:   str
    action:     str
    resource:   Optional[str] = None
    details:    Optional[str] = None
    ip_address: Optional[str] = None
    success:    bool
    created_at: datetime
    model_config = {"from_attributes": True}

class AuditLogListResponse(BaseModel):
    total: int
    items: List[AuditLogResponse]

class DashboardStats(BaseModel):
    total_customers:     int
    total_statements:    int
    total_analyses:      int
    low_risk_count:      int
    moderate_risk_count: int
    high_risk_count:     int
    recent_uploads:      List[dict]
    recent_analyses:     List[dict]

class SuccessResponse(BaseModel):
    success: bool = True
    message: str
    data:    Optional[Any] = None

class ErrorResponse(BaseModel):
    success: bool = False
    error:   str
    detail:  Optional[str] = None
