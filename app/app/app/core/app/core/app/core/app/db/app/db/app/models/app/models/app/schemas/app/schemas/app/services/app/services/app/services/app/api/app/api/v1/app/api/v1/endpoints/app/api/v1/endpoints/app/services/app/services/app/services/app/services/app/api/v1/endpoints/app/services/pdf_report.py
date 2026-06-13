from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak
from datetime import datetime
import io

NAVY   = colors.HexColor("#0A2342")
BLUE   = colors.HexColor("#1D4ED8")
ACCENT = colors.HexColor("#3B82F6")
GREEN  = colors.HexColor("#10B981")
RED    = colors.HexColor("#EF4444")
AMBER  = colors.HexColor("#F59E0B")
LIGHT  = colors.HexColor("#F8FAFC")
SLATE  = colors.HexColor("#64748B")
BORDER = colors.HexColor("#E2E8F0")
WHITE  = colors.white

from app.core.config import settings
CURRENCY = settings.CURRENCY_SYMBOL

def fmt(n): return f"{CURRENCY} {n:,.2f}"
def fmt_short(n):
    if n >= 1_000_000: return f"{CURRENCY} {n/1_000_000:.2f}M"
    if n >= 1_000: return f"{CURRENCY} {n/1_000:.0f}K"
    return f"{CURRENCY} {n:,.2f}"


class PDFReportGenerator:
    def __init__(self, analysis, statement, customer, analyst_name):
        self.analysis = analysis
        self.statement = statement
        self.customer = customer
        self.analyst_name = analyst_name
        self.styles = self._build_styles()

    def generate(self) -> bytes:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=1.8*cm, leftMargin=1.8*cm, topMargin=2.5*cm, bottomMargin=2*cm)
        story = []
        story += self._cover_page()
        story.append(PageBreak())
        story += self._executive_summary()
        story.append(PageBreak())
        story += self._monthly_analysis()
        story.append(PageBreak())
        story += self._credit_metrics()
        story.append(PageBreak())
        story += self._commentary_page()
        story.append(PageBreak())
        story += self._risk_assessment_page()
        doc.build(story, onFirstPage=self._header_footer, onLaterPages=self._header_footer)
        return buf.getvalue()

    def _build_styles(self):
        s = getSampleStyleSheet()
        custom = {
            "H1": ParagraphStyle("H1", fontName="Helvetica-Bold", fontSize=14, textColor=NAVY, spaceBefore=12, spaceAfter=6),
            "H2": ParagraphStyle("H2", fontName="Helvetica-Bold", fontSize=11, textColor=BLUE, spaceBefore=8, spaceAfter=4),
            "Body": ParagraphStyle("Body", fontName="Helvetica", fontSize=9, textColor=NAVY, leading=14, spaceAfter=4, alignment=TA_JUSTIFY),
            "Small": ParagraphStyle("Small", fontName="Helvetica", fontSize=8, textColor=SLATE, spaceAfter=2),
            "Title": ParagraphStyle("Title", fontName="Helvetica-Bold", fontSize=22, textColor=NAVY, spaceAfter=6, alignment=TA_CENTER),
            "SubTitle": ParagraphStyle("SubTitle", fontName="Helvetica", fontSize=11, textColor=SLATE, spaceAfter=4, alignment=TA_CENTER),
        }
        return {**{k: s[k] for k in s.byName}, **custom}

    def _header_footer(self, canvas, doc):
        canvas.saveState()
        w, h = A4
        canvas.setFillColor(NAVY)
        canvas.rect(0, h-1.4*cm, w, 1.4*cm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawString(1.8*cm, h-0.9*cm, "OKEYO ANALYTICS")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(w-1.8*cm, h-0.9*cm, f"CONFIDENTIAL — {self.customer.full_name}")
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, w, 1.1*cm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(1.8*cm, 0.38*cm, f"Generated: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} UTC  |  Analyst: {self.analyst_name}")
        canvas.drawRightString(w-1.8*cm, 0.38*cm, f"Page {doc.page}")
        canvas.restoreState()

    def _cover_page(self):
        a = self.analysis
        risk_label = a.risk_rating.value if hasattr(a.risk_rating, "value") else str(a.risk_rating)
        risk_color = {"LOW": GREEN, "MODERATE": AMBER, "HIGH": RED}.get(risk_label, AMBER)
        elements = [
            Spacer(1, 1.5*cm),
            Paragraph("OKEYO ANALYTICS", self.styles["Title"]),
            Paragraph("Smart Bank Statement Analysis &amp; Credit Intelligence Platform", self.styles["SubTitle"]),
            HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=12),
            Spacer(1, 0.5*cm),
            Paragraph("CREDIT ANALYSIS REPORT", ParagraphStyle("CT", fontName="Helvetica-Bold", fontSize=18, textColor=BLUE, alignment=TA_CENTER, spaceAfter=6)),
            Spacer(1, 0.5*cm),
        ]
        period = f"{a.period_start.strftime('%d %b %Y') if a.period_start else 'N/A'} — {a.period_end.strftime('%d %b %Y') if a.period_end else 'N/A'}"
        info_data = [
            ["Customer Name:", self.customer.full_name, "Account No:", self.customer.account_number],
            ["Bank:", self.customer.bank_name, "Period:", period],
            ["Customer Type:", self.customer.customer_type, "Months:", f"{a.period_months} months"],
            ["Prepared By:", self.analyst_name, "Date:", datetime.utcnow().strftime("%d/%m/%Y")],
        ]
        info_table = Table(info_data, colWidths=[3.5*cm, 6*cm, 3*cm, 5.5*cm])
        info_table.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
            ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
            ("FONTNAME", (2,0), (2,-1), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("ROWBACKGROUNDS", (0,0), (-1,-1), [LIGHT, WHITE]),
            ("GRID", (0,0), (-1,-1), 0.5, BORDER),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
        ]))
        elements += [info_table, Spacer(1, 0.8*cm)]
        kpi_data = [[
            Paragraph(f'<font name="Helvetica" size="8">Total Credits</font><br/><font name="Helvetica-Bold" size="13" color="#10B981">{fmt_short(a.total_credits)}</font>', ParagraphStyle("k", alignment=TA_CENTER, leading=16)),
            Paragraph(f'<font name="Helvetica" size="8">Total Debits</font><br/><font name="Helvetica-Bold" size="13" color="#EF4444">{fmt_short(a.total_debits)}</font>', ParagraphStyle("k", alignment=TA_CENTER, leading=16)),
            Paragraph(f'<font name="Helvetica" size="8">Avg Mo. Credits</font><br/><font name="Helvetica-Bold" size="13" color="#1D4ED8">{fmt_short(a.avg_monthly_credits)}</font>', ParagraphStyle("k", alignment=TA_CENTER, leading=16)),
            Paragraph(f'<font name="Helvetica" size="8">Risk Rating</font><br/><font name="Helvetica-Bold" size="13">{risk_label}</font>', ParagraphStyle("k", alignment=TA_CENTER, leading=16)),
        ]]
        kpi_table = Table(kpi_data, colWidths=[4.4*cm]*4)
        kpi_table.setStyle(TableStyle([
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("BACKGROUND", (0,0), (-1,-1), LIGHT),
            ("BOX", (0,0), (-1,-1), 1, BORDER),
            ("INNERGRID", (0,0), (-1,-1), 0.5, BORDER),
            ("TOPPADDING", (0,0), (-1,-1), 10),
            ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ]))
        elements += [kpi_table]
        return elements

    def _executive_summary(self):
        a = self.analysis
        elements = [Paragraph("1. EXECUTIVE SUMMARY", self.styles["H1"]), HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=8)]
        rows = [["METRIC", "VALUE", "METRIC", "VALUE"],
            ["Total Credits", fmt(a.total_credits), "Total Debits", fmt(a.total_debits)],
            ["Avg Monthly Credits", fmt(a.avg_monthly_credits), "Avg Monthly Debits", fmt(a.avg_monthly_debits)],
            ["Highest Balance", fmt(a.highest_balance), "Lowest Balance", fmt(a.lowest_balance)],
            ["Avg Balance", fmt(a.avg_balance), "Net Flow", fmt(a.net_flow)],
            ["Negative Episodes", str(a.negative_balance_count), "Negative Days", str(a.negative_balance_days)],
            ["Active Months", f"{a.active_months}/{a.period_months}", "Risk Score", f"{a.risk_score}/100"],
            ["Risk Rating", a.risk_rating.value if hasattr(a.risk_rating,"value") else str(a.risk_rating), "Period Days", str(a.period_days)],
        ]
        t = Table(rows, colWidths=[5.5*cm, 4.5*cm, 5.5*cm, 4.5*cm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTNAME", (0,1), (0,-1), "Helvetica-Bold"),
            ("FONTNAME", (2,1), (2,-1), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("BACKGROUND", (0,0), (-1,0), NAVY),
            ("TEXTCOLOR", (0,0), (-1,0), WHITE),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [LIGHT, WHITE]),
            ("GRID", (0,0), (-1,-1), 0.5, BORDER),
            ("ALIGN", (1,0), (1,-1), "RIGHT"),
            ("ALIGN", (3,0), (3,-1), "RIGHT"),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
        ]))
        elements.append(t)
        return elements

    def _monthly_analysis(self):
        a = self.analysis
        elements = [Paragraph("2. MONTHLY ANALYSIS", self.styles["H1"]), HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=8)]
        rows = [["Month", "Credits (KES)", "Debits (KES)", "High Balance", "Low Balance", "Avg Balance", "Txns"]]
        monthly = a.monthly_data or []
        total_cr = total_db = 0.0
        for m in monthly:
            rows.append([f"{m['month']} {m['year']}", f"{m['credits']:,.0f}", f"{m['debits']:,.0f}", f"{m['high_bal']:,.0f}", f"{m['low_bal']:,.0f}", f"{m['avg_bal']:,.0f}", str(m.get('txn_count', 0))])
            total_cr += m['credits']; total_db += m['debits']
        rows.append(["TOTAL", f"{total_cr:,.0f}", f"{total_db:,.0f}", "", "", "", ""])
        t = Table(rows, colWidths=[2.5*cm, 2.9*cm, 2.9*cm, 2.9*cm, 2.9*cm, 2.9*cm, 1.4*cm], repeatRows=1)
        t.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("BACKGROUND", (0,0), (-1,0), NAVY),
            ("TEXTCOLOR", (0,0), (-1,0), WHITE),
            ("BACKGROUND", (0,-1), (-1,-1), LIGHT),
            ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0,1), (-1,-2), [WHITE, LIGHT]),
            ("GRID", (0,0), (-1,-1), 0.4, BORDER),
            ("ALIGN", (1,0), (-1,-1), "RIGHT"),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
            ("TEXTCOLOR", (1,1), (1,-2), GREEN),
            ("TEXTCOLOR", (2,1), (2,-2), RED),
        ]))
        elements.append(t)
        return elements

    def _credit_metrics(self):
        a = self.analysis
        elements = [Paragraph("3. CREDIT METRICS &amp; CONCENTRATION", self.styles["H1"]), HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=8)]
        conc = a.concentration_data or []
        rows = [["#", "Source / Description", "Amount (KES)", "% Contribution", "Transactions"]]
        for i, c in enumerate(conc[:10], 1):
            rows.append([str(i), c["source"], f"{c['amount']:,.0f}", f"{c['pct']:.1f}%", str(c.get("txn_count", 0))])
        t = Table(rows, colWidths=[1*cm, 7.5*cm, 3.5*cm, 3*cm, 3*cm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 8.5),
            ("BACKGROUND", (0,0), (-1,0), NAVY),
            ("TEXTCOLOR", (0,0), (-1,0), WHITE),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, LIGHT]),
            ("GRID", (0,0), (-1,-1), 0.4, BORDER),
            ("ALIGN", (2,0), (-1,-1), "RIGHT"),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
        ]))
        elements.append(t)
        return elements

    def _commentary_page(self):
        a = self.analysis
        elements = [Paragraph("4. AI CREDIT COMMENTARY", self.styles["H1"]), HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=8)]
        commentary = a.ai_commentary or "Commentary not yet generated. Please run AI analysis."
        for para in commentary.split("\n\n"):
            para = para.strip()
            if para:
                elements.append(Paragraph(para, self.styles["Body"]))
                elements.append(Spacer(1, 0.2*cm))
        return elements

    def _risk_assessment_page(self):
        a = self.analysis
        risk_label = a.risk_rating.value if hasattr(a.risk_rating, "value") else str(a.risk_rating)
        risk_color = {"LOW": GREEN, "MODERATE": AMBER, "HIGH": RED}.get(risk_label, AMBER)
        elements = [Paragraph("5. RISK ASSESSMENT", self.styles["H1"]), HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=8)]
        rating_data = [[
            Paragraph(f'<font name="Helvetica-Bold" size="20">{risk_label} RISK</font><br/><font name="Helvetica" size="10">Score: {a.risk_score}/100</font>', ParagraphStyle("r", alignment=TA_CENTER)),
            Paragraph(a.risk_explanation or "", self.styles["Body"])
        ]]
        t = Table(rating_data, colWidths=[4*cm, 14*cm])
        t.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("BOX", (0,0), (-1,-1), 1, BORDER),
            ("INNERGRID", (0,0), (-1,-1), 0.5, BORDER),
            ("BACKGROUND", (0,0), (0,-1), LIGHT),
            ("TOPPADDING", (0,0), (-1,-1), 12),
            ("BOTTOMPADDING", (0,0), (-1,-1), 12),
            ("LEFTPADDING", (0,0), (-1,-1), 10),
        ]))
        elements += [t, Spacer(1, 0.5*cm)]
        score_rows = [["Factor", "Score", "Max", "Rating"]]
        factors = [
            ("Turnover Stability", getattr(a, 'turnover_score', 0) or 0, 25),
            ("Account Conduct", getattr(a, 'conduct_score', 0) or 0, 25),
            ("Growth Trend", getattr(a, 'growth_score', 0) or 0, 20),
            ("Concentration Risk", getattr(a, 'concentration_score', 0) or 0, 15),
            ("Repayment Capacity", a.risk_score, 15),
        ]
        for label, score, max_s in factors:
            pct = score / max_s * 100 if max_s else 0
            rating = "Excellent" if pct >= 80 else "Good" if pct >= 60 else "Fair" if pct >= 40 else "Poor"
            score_rows.append([label, str(score), str(max_s), rating])
        t2 = Table(score_rows, colWidths=[8*cm, 3*cm, 3*cm, 4*cm])
        t2.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("BACKGROUND", (0,0), (-1,0), NAVY),
            ("TEXTCOLOR", (0,0), (-1,0), WHITE),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, LIGHT]),
            ("GRID", (0,0), (-1,-1), 0.4, BORDER),
            ("ALIGN", (1,0), (2,-1), "CENTER"),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
        ]))
        elements.append(t2)
        return elements
