from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from collections import defaultdict
import re


@dataclass
class MonthlyStats:
    month:     str
    year:      int
    month_num: int
    credits:   float = 0.0
    debits:    float = 0.0
    high_bal:  float = 0.0
    low_bal:   float = float('inf')
    avg_bal:   float = 0.0
    txn_count: int = 0


@dataclass
class ConcentrationItem:
    source:    str
    amount:    float
    pct:       float
    txn_count: int


@dataclass
class TrendItem:
    month:      str
    credits:    float
    debits:     float
    mom_growth: Optional[float]
    direction:  str


@dataclass
class RiskResult:
    rating:              str
    score:               int
    explanation:         str
    turnover_score:      int
    conduct_score:       int
    growth_score:        int
    concentration_score: int
    negative_score:      int


@dataclass
class AnalysisResult:
    period_start:          datetime
    period_end:            datetime
    period_months:         int
    period_days:           int
    total_credits:         float
    total_debits:          float
    net_flow:              float
    avg_monthly_credits:   float
    avg_monthly_debits:    float
    avg_balance:           float
    highest_balance:       float
    lowest_balance:        float
    highest_single_credit: float
    highest_single_debit:  float
    highest_credit_date:   Optional[datetime]
    highest_credit_desc:   Optional[str]
    highest_debit_date:    Optional[datetime]
    highest_debit_desc:    Optional[str]
    negative_balance_count: int
    negative_balance_days:  int
    lowest_negative_balance: float
    active_months:         int
    monthly_data:          list
    concentration_data:    list
    trend_data:            list
    risk:                  RiskResult


class AnalysisEngine:
    def __init__(self, transactions: list):
        self.transactions = transactions

    def run(self) -> AnalysisResult:
        if not self.transactions:
            raise ValueError("No transactions to analyse")
        txns = sorted(self.transactions, key=lambda t: t.txn_date)
        period_start  = txns[0].txn_date
        period_end    = txns[-1].txn_date
        period_days   = (period_end.date() - period_start.date()).days + 1
        period_months = max(1, round(period_days / 30.44))
        total_credits = sum(t.credit for t in txns)
        total_debits  = sum(t.debit  for t in txns)
        net_flow      = total_credits - total_debits
        balances      = [t.balance for t in txns if t.balance is not None]
        highest_balance = max(balances) if balances else 0.0
        lowest_balance  = min(balances) if balances else 0.0
        avg_balance     = sum(balances) / len(balances) if balances else 0.0
        credit_txns = [t for t in txns if t.credit > 0]
        debit_txns  = [t for t in txns if t.debit  > 0]
        top_credit  = max(credit_txns, key=lambda t: t.credit) if credit_txns else None
        top_debit   = max(debit_txns,  key=lambda t: t.debit)  if debit_txns  else None
        avg_monthly_credits = total_credits / period_months
        avg_monthly_debits  = total_debits  / period_months
        neg_count, neg_days, lowest_neg = self._negative_analysis(txns)
        monthly = self._monthly_breakdown(txns)
        active_months = len([m for m in monthly if m.credits > 0 or m.debits > 0])
        concentration = self._concentration_analysis(txns, total_credits)
        trends = self._trend_analysis(monthly)
        risk = self._risk_assessment(
            avg_monthly_credits=avg_monthly_credits,
            total_credits=total_credits,
            period_months=period_months,
            neg_count=neg_count,
            neg_days=neg_days,
            monthly=monthly,
            concentration=concentration,
            trends=trends,
        )
        return AnalysisResult(
            period_start=period_start, period_end=period_end,
            period_months=period_months, period_days=period_days,
            total_credits=round(total_credits, 2), total_debits=round(total_debits, 2),
            net_flow=round(net_flow, 2),
            avg_monthly_credits=round(avg_monthly_credits, 2),
            avg_monthly_debits=round(avg_monthly_debits, 2),
            avg_balance=round(avg_balance, 2),
            highest_balance=round(highest_balance, 2), lowest_balance=round(lowest_balance, 2),
            highest_single_credit=round(top_credit.credit, 2) if top_credit else 0.0,
            highest_single_debit=round(top_debit.debit, 2)    if top_debit  else 0.0,
            highest_credit_date=top_credit.txn_date if top_credit else None,
            highest_credit_desc=top_credit.description[:200] if top_credit else None,
            highest_debit_date=top_debit.txn_date   if top_debit  else None,
            highest_debit_desc=top_debit.description[:200]  if top_debit  else None,
            negative_balance_count=neg_count, negative_balance_days=neg_days,
            lowest_negative_balance=round(lowest_neg, 2),
            active_months=active_months,
            monthly_data=monthly, concentration_data=concentration, trend_data=trends,
            risk=risk,
        )

    def _monthly_breakdown(self, txns):
        buckets = {}
        for t in txns:
            key = (t.txn_date.year, t.txn_date.month)
            if key not in buckets:
                month_name = t.txn_date.strftime("%b")
                buckets[key] = MonthlyStats(month=month_name, year=t.txn_date.year, month_num=t.txn_date.month, low_bal=float('inf'))
            m = buckets[key]
            m.credits   += t.credit
            m.debits    += t.debit
            m.txn_count += 1
            if t.balance is not None:
                m.high_bal = max(m.high_bal, t.balance)
                m.low_bal  = min(m.low_bal,  t.balance)
        for m in buckets.values():
            if m.low_bal == float('inf'):
                m.low_bal = 0.0
            m.avg_bal = round((m.high_bal + m.low_bal) / 2, 2)
            m.credits = round(m.credits, 2)
            m.debits  = round(m.debits,  2)
        return sorted(buckets.values(), key=lambda x: (x.year, x.month_num))

    def _negative_analysis(self, txns):
        neg_count = neg_days = 0
        lowest_neg = 0.0
        was_neg = False
        for t in txns:
            if t.balance is not None and t.balance < 0:
                if not was_neg:
                    neg_count += 1
                was_neg = True
                neg_days += 1
                lowest_neg = min(lowest_neg, t.balance)
            else:
                was_neg = False
        return neg_count, neg_days, lowest_neg

    def _concentration_analysis(self, txns, total_credits):
        sources = defaultdict(lambda: {"amount": 0.0, "count": 0})
        for t in txns:
            if t.credit <= 0:
                continue
            source = self._normalize_source(t.description)
            sources[source]["amount"] += t.credit
            sources[source]["count"]  += 1
        items = [
            ConcentrationItem(source=src, amount=round(data["amount"], 2),
                pct=round(data["amount"] / total_credits * 100, 1) if total_credits > 0 else 0.0,
                txn_count=data["count"])
            for src, data in sources.items()
        ]
        items.sort(key=lambda x: x.amount, reverse=True)
        return items[:10]

    def _normalize_source(self, desc: str) -> str:
        desc = desc.upper().strip()
        desc = re.sub(r'\d{6,}', '', desc)
        desc = re.sub(r'\b\d+\.\d+\b', '', desc)
        desc = re.sub(r'\s+', ' ', desc).strip()
        return " ".join(desc.split()[:4])

    def _trend_analysis(self, monthly):
        trends = []
        for i, m in enumerate(monthly):
            if i == 0:
                mom = None
                direction = "Stable"
            else:
                prev = monthly[i-1].credits
                if prev > 0:
                    mom = round((m.credits - prev) / prev * 100, 1)
                    direction = "Growing" if mom > 5 else "Declining" if mom < -5 else "Stable"
                else:
                    mom = None
                    direction = "Stable"
            trends.append(TrendItem(month=f"{m.month} {m.year}", credits=m.credits, debits=m.debits, mom_growth=mom, direction=direction))
        return trends

    def _risk_assessment(self, avg_monthly_credits, total_credits, period_months, neg_count, neg_days, monthly, concentration, trends):
        if monthly:
            credits_list = [m.credits for m in monthly if m.credits > 0]
            if len(credits_list) >= 2:
                mean = sum(credits_list) / len(credits_list)
                variance = sum((x - mean)**2 for x in credits_list) / len(credits_list)
                cv = (variance**0.5 / mean) if mean > 0 else 1.0
                turnover_score = max(0, min(25, int(25 * (1 - min(cv, 1.0)))))
            else:
                turnover_score = 10
        else:
            turnover_score = 0
        neg_ratio = neg_days / max(period_months * 30, 1)
        if neg_count == 0:
            conduct_score = 25
        elif neg_count <= 2 and neg_ratio < 0.05:
            conduct_score = 18
        elif neg_count <= 5 and neg_ratio < 0.15:
            conduct_score = 10
        else:
            conduct_score = 3
        growing  = sum(1 for t in trends if t.direction == "Growing")
        declining = sum(1 for t in trends if t.direction == "Declining")
        total_months = len(trends)
        if total_months > 0:
            growth_score = max(0, min(20, int(20 * (growing / total_months - declining / total_months * 0.5 + 0.5))))
        else:
            growth_score = 10
        if concentration:
            top_pct  = concentration[0].pct if concentration else 0
            top2_pct = sum(c.pct for c in concentration[:2])
            if top_pct < 30 and top2_pct < 50:
                concentration_score = 15
            elif top_pct < 50 and top2_pct < 70:
                concentration_score = 10
            elif top_pct < 70:
                concentration_score = 6
            else:
                concentration_score = 2
        else:
            concentration_score = 8
        if avg_monthly_credits >= 1_000_000:
            capacity_score = 15
        elif avg_monthly_credits >= 500_000:
            capacity_score = 12
        elif avg_monthly_credits >= 100_000:
            capacity_score = 8
        else:
            capacity_score = 4
        total_score = turnover_score + conduct_score + growth_score + concentration_score + capacity_score
        if total_score >= 70:
            rating = "LOW"
            explanation = "Account demonstrates strong financial conduct with consistent credit inflows and minimal adverse indicators."
        elif total_score >= 45:
            rating = "MODERATE"
            explanation = "Account shows reasonable transactional activity with some areas of concern. Additional due diligence recommended."
        else:
            rating = "HIGH"
            explanation = "Account exhibits significant risk indicators. Credit facility requires enhanced scrutiny."
        return RiskResult(rating=rating, score=total_score, explanation=explanation,
            turnover_score=turnover_score, conduct_score=conduct_score,
            growth_score=growth_score, concentration_score=concentration_score,
            negative_score=conduct_score)
