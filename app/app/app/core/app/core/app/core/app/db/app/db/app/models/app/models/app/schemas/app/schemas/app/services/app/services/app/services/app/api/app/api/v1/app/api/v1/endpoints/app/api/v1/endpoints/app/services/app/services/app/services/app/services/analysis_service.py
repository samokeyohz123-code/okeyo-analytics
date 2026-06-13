from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.models import Analysis, Transaction, Statement, RiskRating
from app.services.analysis_engine import AnalysisEngine
from app.services.parser import RawTransaction
from app.core.config import settings
from datetime import datetime
from typing import Optional
from loguru import logger


class AnalysisService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_analysis(self, statement_id: int, analyst_id: int) -> Analysis:
        r = await self.db.execute(select(Transaction).where(Transaction.statement_id == statement_id).order_by(Transaction.txn_date))
        db_txns = r.scalars().all()
        if not db_txns:
            raise ValueError("No transactions found for this statement")
        raw = [RawTransaction(txn_date=t.txn_date, description=t.description, credit=t.credit, debit=t.debit, balance=t.balance, reference=t.reference) for t in db_txns]
        logger.info(f"Running analysis on statement {statement_id} ({len(raw)} transactions)")
        result = AnalysisEngine(raw).run()
        existing_r = await self.db.execute(select(Analysis).where(Analysis.statement_id == statement_id))
        analysis = existing_r.scalar_one_or_none()
        risk_map = {"LOW": RiskRating.low, "MODERATE": RiskRating.moderate, "HIGH": RiskRating.high}
        monthly_json = [{"month":m.month,"year":m.year,"month_num":m.month_num,"credits":m.credits,"debits":m.debits,"high_bal":m.high_bal,"low_bal":m.low_bal,"avg_bal":m.avg_bal,"txn_count":m.txn_count} for m in result.monthly_data]
        concentration_json = [{"source":c.source,"amount":c.amount,"pct":c.pct,"txn_count":c.txn_count} for c in result.concentration_data]
        trend_json = [{"month":t.month,"credits":t.credits,"debits":t.debits,"mom_growth":t.mom_growth,"direction":t.direction} for t in result.trend_data]
        fields = dict(
            statement_id=statement_id, analyst_id=analyst_id,
            period_start=result.period_start, period_end=result.period_end,
            period_months=result.period_months, period_days=result.period_days,
            total_credits=result.total_credits, total_debits=result.total_debits, net_flow=result.net_flow,
            avg_monthly_credits=result.avg_monthly_credits, avg_monthly_debits=result.avg_monthly_debits,
            avg_balance=result.avg_balance, highest_balance=result.highest_balance, lowest_balance=result.lowest_balance,
            highest_single_credit=result.highest_single_credit, highest_single_debit=result.highest_single_debit,
            highest_credit_date=result.highest_credit_date, highest_credit_desc=result.highest_credit_desc,
            highest_debit_date=result.highest_debit_date, highest_debit_desc=result.highest_debit_desc,
            negative_balance_count=result.negative_balance_count, negative_balance_days=result.negative_balance_days,
            lowest_negative_balance=result.lowest_negative_balance, active_months=result.active_months,
            risk_rating=risk_map.get(result.risk.rating, RiskRating.moderate),
            risk_score=result.risk.score, risk_explanation=result.risk.explanation,
            turnover_score=result.risk.turnover_score, conduct_score=result.risk.conduct_score,
            growth_score=result.risk.growth_score, concentration_score=result.risk.concentration_score,
            monthly_data=monthly_json, concentration_data=concentration_json, trend_data=trend_json,
        )
        if analysis:
            for k, v in fields.items():
                setattr(analysis, k, v)
        else:
            analysis = Analysis(**fields)
            self.db.add(analysis)
        await self.db.flush()
        await self.db.refresh(analysis)
        logger.info(f"Analysis complete: {result.risk.rating} RISK (score {result.risk.score})")
        return analysis

    async def generate_ai_commentary(self, statement_id: int, force: bool = False) -> str:
        r = await self.db.execute(select(Analysis).where(Analysis.statement_id == statement_id))
        analysis = r.scalar_one_or_none()
        if not analysis:
            raise ValueError("Analysis not found. Run analysis first.")
        if analysis.ai_commentary and not force:
            return analysis.ai_commentary
        stmt_r = await self.db.execute(select(Statement).where(Statement.id == statement_id))
        stmt = stmt_r.scalar_one_or_none()
        period = f"{analysis.period_start.strftime('%B %Y') if analysis.period_start else 'N/A'} to {analysis.period_end.strftime('%B %Y') if analysis.period_end else 'N/A'}"
        currency = settings.DEFAULT_CURRENCY
        prompt = f"""You are a Senior Credit Analyst at a commercial bank in Kenya writing an official credit commentary.

STATEMENT ANALYSIS DATA:
- Review Period: {period} ({analysis.period_months} months)
- Total Credits: {currency} {analysis.total_credits:,.2f}
- Total Debits: {currency} {analysis.total_debits:,.2f}
- Average Monthly Credits: {currency} {analysis.avg_monthly_credits:,.2f}
- Average Monthly Debits: {currency} {analysis.avg_monthly_debits:,.2f}
- Highest Balance: {currency} {analysis.highest_balance:,.2f}
- Lowest Balance: {currency} {analysis.lowest_balance:,.2f}
- Negative Balance Episodes: {analysis.negative_balance_count} times ({analysis.negative_balance_days} days)
- Active Months: {analysis.active_months} of {analysis.period_months}
- Risk Rating: {analysis.risk_rating.value if hasattr(analysis.risk_rating, 'value') else analysis.risk_rating} (Score: {analysis.risk_score}/100)

Write a formal professional credit commentary in 5 paragraphs covering:
1. Account Activity Analysis
2. Turnover Analysis
3. Balance Conduct Analysis
4. Trend Analysis
5. Repayment Capacity Assessment

Use formal banking language. Be specific with figures. No bullet points. Flowing prose only."""

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            message = client.messages.create(model=settings.AI_MODEL, max_tokens=settings.AI_MAX_TOKENS, messages=[{"role": "user", "content": prompt}])
            commentary = message.content[0].text
        except Exception as e:
            logger.warning(f"Anthropic API error: {e} — using fallback commentary")
            risk_word = {"LOW": "satisfactory", "MODERATE": "acceptable", "HIGH": "below-par"}.get(
                analysis.risk_rating.value if hasattr(analysis.risk_rating, "value") else str(analysis.risk_rating), "satisfactory")
            commentary = (
                f"The account demonstrates {risk_word} transactional performance during the {period} review period. "
                f"A total of {currency} {analysis.total_credits:,.2f} was credited to the account, translating to average monthly credit turnovers of {currency} {analysis.avg_monthly_credits:,.2f}.\n\n"
                f"Credit turnover patterns indicate {'consistent and growing' if analysis.risk_score >= 70 else 'variable'} inflows across the review period. "
                f"The account was active for {analysis.active_months} of the {analysis.period_months} review months.\n\n"
                f"Balance conduct was {'commendable with no negative balance episodes recorded' if analysis.negative_balance_count == 0 else f'noted with {analysis.negative_balance_count} negative balance episode(s)'}. "
                f"The highest recorded balance stood at {currency} {analysis.highest_balance:,.2f}.\n\n"
                f"Trend analysis indicates {'an upward trajectory' if analysis.risk_score >= 70 else 'mixed performance requiring monitoring'}.\n\n"
                f"Based on the foregoing, the account turnovers {'indicate sufficient repayment capacity' if analysis.risk_score >= 50 else 'require additional security measures'}. "
                f"The account is rated {analysis.risk_rating.value if hasattr(analysis.risk_rating, 'value') else analysis.risk_rating} RISK with a score of {analysis.risk_score}/100."
            )
        analysis.ai_commentary = commentary
        analysis.ai_generated_at = datetime.utcnow()
        await self.db.flush()
        return commentary

    async def get_by_statement(self, statement_id: int) -> Optional[Analysis]:
        r = await self.db.execute(select(Analysis).where(Analysis.statement_id == statement_id))
        return r.scalar_one_or_none()
