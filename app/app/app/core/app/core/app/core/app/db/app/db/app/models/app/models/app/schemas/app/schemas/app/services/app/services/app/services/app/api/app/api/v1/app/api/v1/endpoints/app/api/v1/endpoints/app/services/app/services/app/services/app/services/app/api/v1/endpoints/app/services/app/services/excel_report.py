import io
import xlsxwriter
from datetime import datetime
from app.core.config import settings

CURRENCY = settings.CURRENCY_SYMBOL


class ExcelReportGenerator:
    def __init__(self, analysis, statement, customer, transactions, analyst_name):
        self.analysis     = analysis
        self.statement    = statement
        self.customer     = customer
        self.transactions = transactions
        self.analyst_name = analyst_name

    def generate(self) -> bytes:
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {"in_memory": True, "default_date_format": "dd/mm/yyyy"})
        self.fmt = self._build_formats(wb)
        self._sheet_transactions(wb)
        self._sheet_monthly(wb)
        self._sheet_metrics(wb)
        self._sheet_trends(wb)
        self._sheet_risk(wb)
        self._sheet_commentary(wb)
        wb.close()
        return buf.getvalue()

    def _build_formats(self, wb):
        navy = "#0A2342"; blue = "#1D4ED8"; green = "#10B981"
        red = "#EF4444"; light = "#F8FAFC"; border = "#E2E8F0"
        f = {}
        base = {"font_name": "Calibri", "font_size": 10, "valign": "vcenter"}
        f["title"]   = wb.add_format({**base, "bold": True, "font_size": 16, "font_color": navy, "border": 0})
        f["subtitle"]= wb.add_format({**base, "font_size": 10, "font_color": "#64748B", "border": 0})
        f["hdr"]     = wb.add_format({**base, "bold": True, "bg_color": navy, "font_color": "white", "border": 1, "border_color": border, "align": "center"})
        f["hdr_left"]= wb.add_format({**base, "bold": True, "bg_color": navy, "font_color": "white", "border": 1, "border_color": border})
        f["row_a"]   = wb.add_format({**base, "bg_color": light, "border": 1, "border_color": border})
        f["row_b"]   = wb.add_format({**base, "bg_color": "white", "border": 1, "border_color": border})
        f["row_a_r"] = wb.add_format({**base, "bg_color": light, "border": 1, "border_color": border, "num_format": f'"{CURRENCY}" #,##0.00', "align": "right"})
        f["row_b_r"] = wb.add_format({**base, "bg_color": "white", "border": 1, "border_color": border, "num_format": f'"{CURRENCY}" #,##0.00', "align": "right"})
        f["row_a_d"] = wb.add_format({**base, "bg_color": light, "border": 1, "border_color": border, "num_format": "dd/mm/yyyy"})
        f["row_b_d"] = wb.add_format({**base, "bg_color": "white", "border": 1, "border_color": border, "num_format": "dd/mm/yyyy"})
        f["credit"]  = wb.add_format({**base, "bg_color": "#D1FAE5", "font_color": "#065F46", "border": 1, "border_color": border, "num_format": f'"{CURRENCY}" #,##0.00', "align": "right", "bold": True})
        f["debit"]   = wb.add_format({**base, "bg_color": "#FEE2E2", "font_color": "#991B1B", "border": 1, "border_color": border, "num_format": f'"{CURRENCY}" #,##0.00', "align": "right", "bold": True})
        f["zero"]    = wb.add_format({**base, "bg_color": "white", "font_color": "#CBD5E1", "border": 1, "border_color": border, "align": "center"})
        f["total"]   = wb.add_format({**base, "bold": True, "bg_color": navy, "font_color": "white", "border": 1, "border_color": border, "num_format": f'"{CURRENCY}" #,##0.00', "align": "right"})
        f["total_l"] = wb.add_format({**base, "bold": True, "bg_color": navy, "font_color": "white", "border": 1, "border_color": border})
        f["low_risk"]= wb.add_format({**base, "bold": True, "bg_color": "#D1FAE5", "font_color": "#065F46", "border": 1, "border_color": border, "align": "center"})
        f["mod_risk"]= wb.add_format({**base, "bold": True, "bg_color": "#FEF3C7", "font_color": "#92400E", "border": 1, "border_color": border, "align": "center"})
        f["hi_risk"] = wb.add_format({**base, "bold": True, "bg_color": "#FEE2E2", "font_color": "#991B1B", "border": 1, "border_color": border, "align": "center"})
        f["label"]   = wb.add_format({**base, "bold": True, "font_color": navy, "bg_color": light, "border": 1, "border_color": border})
        f["value"]   = wb.add_format({**base, "font_color": "#334155", "bg_color": "white", "border": 1, "border_color": border})
        f["value_r"] = wb.add_format({**base, "font_color": "#334155", "bg_color": "white", "border": 1, "border_color": border, "num_format": f'"{CURRENCY}" #,##0.00', "align": "right"})
        f["wrap"]    = wb.add_format({**base, "text_wrap": True, "valign": "top", "border": 1, "border_color": border})
        f["pct"]     = wb.add_format({**base, "bg_color": "white", "border": 1, "border_color": border, "num_format": "0.0%", "align": "right"})
        return f

    def _write_header_banner(self, ws, title, subtitle, cols):
        ws.merge_range(0, 0, 0, cols-1, f"OKEYO ANALYTICS — {title}", self.fmt["title"])
        ws.merge_range(1, 0, 1, cols-1, subtitle, self.fmt["subtitle"])
        ws.set_row(0, 22); ws.set_row(1, 16)

    def _sheet_transactions(self, wb):
        ws = wb.add_worksheet("1. Transactions")
        ws.set_tab_color("#1D4ED8"); ws.freeze_panes(4, 0); ws.set_zoom(90)
        self._write_header_banner(ws, "RAW TRANSACTIONS", f"Customer: {self.customer.full_name} | Account: {self.customer.account_number} | Bank: {self.customer.bank_name}", 6)
        headers = ["Date", "Description", "Credit (KES)", "Debit (KES)", "Balance (KES)", "Reference"]
        widths  = [14, 50, 18, 18, 18, 20]
        for i, (h, w) in enumerate(zip(headers, widths)):
            ws.write(3, i, h, self.fmt["hdr"]); ws.set_column(i, i, w)
        for row_i, txn in enumerate(self.transactions, 4):
            bg = self.fmt["row_a"] if row_i%2==0 else self.fmt["row_b"]
            bg_r = self.fmt["row_a_r"] if row_i%2==0 else self.fmt["row_b_r"]
            bg_d = self.fmt["row_a_d"] if row_i%2==0 else self.fmt["row_b_d"]
            ws.write_datetime(row_i, 0, txn.txn_date, bg_d)
            ws.write_string(row_i, 1, txn.description, bg)
            ws.write_number(row_i, 2, txn.credit, self.fmt["credit"] if txn.credit > 0 else self.fmt["zero"])
            ws.write_number(row_i, 3, txn.debit,  self.fmt["debit"]  if txn.debit  > 0 else self.fmt["zero"])
            ws.write_number(row_i, 4, txn.balance or 0, bg_r)
            ws.write_string(row_i, 5, txn.reference or "", bg)
        tr = len(self.transactions) + 4
        ws.write(tr, 0, "TOTALS", self.fmt["total_l"]); ws.write(tr, 1, "", self.fmt["total_l"])
        ws.write_number(tr, 2, sum(t.credit for t in self.transactions), self.fmt["total"])
        ws.write_number(tr, 3, sum(t.debit  for t in self.transactions), self.fmt["total"])
        ws.write(tr, 4, "", self.fmt["total"]); ws.write(tr, 5, "", self.fmt["total"])
        ws.autofilter(3, 0, 3+len(self.transactions), 5)

    def _sheet_monthly(self, wb):
        ws = wb.add_worksheet("2. Monthly Analysis")
        ws.set_tab_color("#10B981"); ws.set_zoom(90)
        monthly = self.analysis.monthly_data or []
        a = self.analysis
        self._write_header_banner(ws, "MONTHLY ANALYSIS", f"Period: {a.period_start.strftime('%b %Y') if a.period_start else 'N/A'} — {a.period_end.strftime('%b %Y') if a.period_end else 'N/A'}", 7)
        headers = ["Month", "Credits (KES)", "Debits (KES)", "Highest Balance", "Lowest Balance", "Avg Balance", "Transactions"]
        widths  = [14, 18, 18, 18, 18, 18, 14]
        for i, (h, w) in enumerate(zip(headers, widths)):
            ws.write(3, i, h, self.fmt["hdr"]); ws.set_column(i, i, w)
        total_cr = total_db = 0.0
        for r, m in enumerate(monthly, 4):
            bg   = self.fmt["row_a"]   if r%2==0 else self.fmt["row_b"]
            bg_r = self.fmt["row_a_r"] if r%2==0 else self.fmt["row_b_r"]
            ws.write(r, 0, f"{m['month']} {m['year']}", bg)
            ws.write_number(r, 1, m["credits"],  self.fmt["credit"])
            ws.write_number(r, 2, m["debits"],   self.fmt["debit"])
            ws.write_number(r, 3, m["high_bal"], bg_r)
            ws.write_number(r, 4, m["low_bal"],  bg_r)
            ws.write_number(r, 5, m["avg_bal"],  bg_r)
            ws.write_number(r, 6, m.get("txn_count", 0), bg)
            total_cr += m["credits"]; total_db += m["debits"]
        tr = len(monthly) + 4
        ws.write(tr, 0, "TOTAL", self.fmt["total_l"])
        ws.write_number(tr, 1, total_cr, self.fmt["total"])
        ws.write_number(tr, 2, total_db, self.fmt["total"])
        for c in range(3, 7): ws.write(tr, c, "", self.fmt["total"])

    def _sheet_metrics(self, wb):
        ws = wb.add_worksheet("3. Credit Metrics")
        ws.set_tab_color("#3B82F6")
        ws.set_column(0, 0, 30); ws.set_column(1, 1, 24); ws.set_column(2, 2, 30); ws.set_column(3, 3, 24)
        self._write_header_banner(ws, "CREDIT METRICS", f"Customer: {self.customer.full_name}", 4)
        a = self.analysis
        risk_label = a.risk_rating.value if hasattr(a.risk_rating, "value") else str(a.risk_rating)
        risk_fmt = {"LOW": self.fmt["low_risk"], "MODERATE": self.fmt["mod_risk"], "HIGH": self.fmt["hi_risk"]}.get(risk_label, self.fmt["mod_risk"])
        pairs = [
            ("Total Credits", a.total_credits, "Total Debits", a.total_debits),
            ("Avg Monthly Credits", a.avg_monthly_credits, "Avg Monthly Debits", a.avg_monthly_debits),
            ("Highest Balance", a.highest_balance, "Lowest Balance", a.lowest_balance),
            ("Average Balance", a.avg_balance, "Net Flow", a.net_flow),
            ("Highest Single Credit", a.highest_single_credit, "Highest Single Debit", a.highest_single_debit),
            ("Period Months", a.period_months, "Active Months", a.active_months),
            ("Neg. Balance Episodes", a.negative_balance_count, "Neg. Balance Days", a.negative_balance_days),
            ("Risk Score", a.risk_score, "Risk Rating", risk_label),
        ]
        for r, (l1, v1, l2, v2) in enumerate(pairs, 4):
            ws.write(r, 0, l1, self.fmt["label"]); ws.write(r, 2, l2, self.fmt["label"])
            if isinstance(v1, float): ws.write_number(r, 1, v1, self.fmt["value_r"])
            else: ws.write(r, 1, v1, self.fmt["value"])
            if r == 4+len(pairs)-1 and isinstance(v2, str): ws.write(r, 3, v2, risk_fmt)
            elif isinstance(v2, float): ws.write_number(r, 3, v2, self.fmt["value_r"])
            else: ws.write(r, 3, v2, self.fmt["value"])

    def _sheet_trends(self, wb):
        ws = wb.add_worksheet("4. Trend Analysis")
        ws.set_tab_color("#F59E0B")
        trends = self.analysis.trend_data or []
        self._write_header_banner(ws, "TREND ANALYSIS", "Month-on-Month Growth Analysis", 5)
        headers = ["Month", "Credits (KES)", "Debits (KES)", "MoM Growth %", "Direction"]
        widths  = [16, 18, 18, 16, 14]
        for i, (h, w) in enumerate(zip(headers, widths)):
            ws.write(3, i, h, self.fmt["hdr"]); ws.set_column(i, i, w)
        for r, t in enumerate(trends, 4):
            bg   = self.fmt["row_a"]   if r%2==0 else self.fmt["row_b"]
            bg_r = self.fmt["row_a_r"] if r%2==0 else self.fmt["row_b_r"]
            ws.write(r, 0, t["month"], bg)
            ws.write_number(r, 1, t["credits"], bg_r)
            ws.write_number(r, 2, t["debits"],  bg_r)
            mom = t.get("mom_growth")
            if mom is not None: ws.write_number(r, 3, mom/100, self.fmt["pct"])
            else: ws.write(r, 3, "—", bg)
            direction = t.get("direction", "")
            dir_fmt = self.fmt["low_risk"] if direction == "Growing" else self.fmt["hi_risk"] if direction == "Declining" else self.fmt["mod_risk"]
            ws.write(r, 4, direction, dir_fmt)

    def _sheet_risk(self, wb):
        ws = wb.add_worksheet("5. Risk Assessment")
        ws.set_tab_color("#EF4444")
        ws.set_column(0, 0, 32); ws.set_column(1, 1, 14); ws.set_column(2, 2, 14); ws.set_column(3, 3, 40)
        a = self.analysis
        risk_label = a.risk_rating.value if hasattr(a.risk_rating, "value") else str(a.risk_rating)
        risk_fmt = {"LOW": self.fmt["low_risk"], "MODERATE": self.fmt["mod_risk"], "HIGH": self.fmt["hi_risk"]}.get(risk_label, self.fmt["mod_risk"])
        self._write_header_banner(ws, "RISK ASSESSMENT", f"Overall Rating: {risk_label} RISK | Score: {a.risk_score}/100", 4)
        ws.write(3, 0, "OVERALL RISK RATING", self.fmt["hdr_left"])
        ws.merge_range(3, 1, 3, 3, risk_label + " RISK", risk_fmt)
        ws.merge_range(4, 0, 4, 3, a.risk_explanation or "", self.fmt["wrap"])
        ws.set_row(4, 60)
        headers = ["Risk Factor", "Score", "Max Score", "Commentary"]
        for i, h in enumerate(headers): ws.write(6, i, h, self.fmt["hdr"])
        factors = [
            ("Turnover Stability",  getattr(a, 'turnover_score', 0) or 0,      25, "Consistency of credit inflows across the review period"),
            ("Account Conduct",     getattr(a, 'conduct_score', 0) or 0,       25, "Negative balance episodes and overall conduct"),
            ("Growth Trend",        getattr(a, 'growth_score', 0) or 0,        20, "Month-on-month credit growth trajectory"),
            ("Concentration Risk",  getattr(a, 'concentration_score', 0) or 0, 15, "Dependency on single or few credit sources"),
            ("Repayment Capacity",  a.risk_score,                              15, "Estimated ability to service proposed credit facility"),
        ]
        for r, (label, score, max_s, note) in enumerate(factors, 7):
            bg = self.fmt["row_a"] if r%2==0 else self.fmt["row_b"]
            ws.write(r, 0, label, self.fmt["label"])
            ws.write(r, 1, f"{score}/{max_s}", bg)
            ws.write(r, 2, str(max_s), bg)
            ws.write(r, 3, note, bg)

    def _sheet_commentary(self, wb):
        ws = wb.add_worksheet("6. AI Commentary")
        ws.set_tab_color("#8B5CF6"); ws.set_column(0, 0, 100)
        self._write_header_banner(ws, "AI CREDIT COMMENTARY", f"Generated by Claude AI | Analyst: {self.analyst_name}", 1)
        commentary = self.analysis.ai_commentary or "Commentary not yet generated."
        row = 4
        for para in commentary.split("\n\n"):
            para = para.strip()
            if para:
                ws.set_row(row, max(60, len(para)//2))
                ws.write(row, 0, para, self.fmt["wrap"])
                row += 2
        ws.write(row, 0, f"Report generated: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} UTC | OKEYO Analytics v{settings.APP_VERSION}", self.fmt["subtitle"])
