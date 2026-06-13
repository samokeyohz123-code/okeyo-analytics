import re
import io
import pandas as pd
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
from loguru import logger
from dateutil import parser as dateparser


@dataclass
class RawTransaction:
    txn_date:    datetime
    description: str
    credit:      float
    debit:       float
    balance:     Optional[float]
    reference:   Optional[str] = None
    raw_row:     Optional[int] = None


MONTHS = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}

def _month_num(name: str) -> str:
    return str(MONTHS.get(name.lower()[:3], 1)).zfill(2)

def normalize_date(raw: str) -> Optional[datetime]:
    if not raw or not str(raw).strip():
        return None
    raw = str(raw).strip()
    patterns = [
        (r'\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b', lambda m: f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"),
        (r'\b(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})\b', lambda m: f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"),
        (r'\b(\d{1,2})[/\-\s]([A-Za-z]{3})[/\-\s](\d{4})\b', lambda m: f"{m.group(3)}-{_month_num(m.group(2))}-{m.group(1).zfill(2)}"),
        (r'\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b', lambda m: f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"),
    ]
    for pattern, formatter in patterns:
        m = re.search(pattern, raw, re.IGNORECASE)
        if m:
            try:
                return datetime.strptime(formatter(m), "%Y-%m-%d")
            except Exception:
                continue
    try:
        return dateparser.parse(raw, dayfirst=True)
    except Exception:
        return None

def clean_amount(val) -> float:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    s = str(val).strip()
    s = re.sub(r'[KkEeSs$£€,\s]', '', s)
    s = s.replace('(', '-').replace(')', '')
    s = re.sub(r'[^\d.\-]', '', s)
    try:
        return abs(float(s)) if s not in ['', '-', '.'] else 0.0
    except Exception:
        return 0.0


class ExcelCSVParser:
    def __init__(self, file_bytes: bytes, file_type: str):
        self.file_bytes = file_bytes
        self.file_type  = file_type.lower()

    def parse(self) -> list:
        try:
            df = self._read_file()
            return self._extract_transactions(df)
        except Exception as e:
            logger.error(f"Excel/CSV parse error: {e}")
            return []

    def _read_file(self) -> pd.DataFrame:
        buf = io.BytesIO(self.file_bytes)
        if self.file_type == "csv":
            for enc in ["utf-8", "latin-1", "cp1252"]:
                try:
                    buf.seek(0)
                    return pd.read_csv(buf, encoding=enc, dtype=str, skip_blank_lines=True)
                except UnicodeDecodeError:
                    continue
            raise ValueError("Cannot read CSV file")
        else:
            return pd.read_excel(buf, dtype=str, engine="openpyxl")

    def _extract_transactions(self, df: pd.DataFrame) -> list:
        df.columns = [str(c).strip().lower() for c in df.columns]
        df = self._find_data_start(df)
        col_map = {}
        for col in df.columns:
            c = col.strip().lower()
            if not col_map.get("date") and any(kw in c for kw in ["date","txn date","value date","trans date","posting"]):
                col_map["date"] = col
            elif not col_map.get("description") and any(kw in c for kw in ["narration","description","details","particulars","remarks","memo"]):
                col_map["description"] = col
            elif not col_map.get("credit") and any(kw in c for kw in ["credit","deposit","cr amount","money in"]):
                col_map["credit"] = col
            elif not col_map.get("debit") and any(kw in c for kw in ["debit","withdrawal","dr amount","money out"]):
                col_map["debit"] = col
            elif not col_map.get("balance") and any(kw in c for kw in ["balance","running balance"]):
                col_map["balance"] = col
            elif not col_map.get("amount") and c == "amount":
                col_map["amount"] = col
        if "date" not in col_map:
            raise ValueError("Cannot find date column in spreadsheet")
        transactions = []
        for row_num, (_, row) in enumerate(df.iterrows()):
            dt = normalize_date(str(row.get(col_map["date"], "")))
            if not dt:
                continue
            desc = str(row.get(col_map.get("description", ""), "TRANSACTION")).strip()
            desc = re.sub(r'\s+', ' ', desc)
            credit  = clean_amount(row.get(col_map["credit"]))  if "credit"  in col_map else 0.0
            debit   = clean_amount(row.get(col_map["debit"]))   if "debit"   in col_map else 0.0
            balance = clean_amount(row.get(col_map["balance"])) if "balance" in col_map else None
            if "amount" in col_map and not credit and not debit:
                raw_amt = str(row.get(col_map["amount"], "0"))
                amt = clean_amount(raw_amt)
                if "-" in raw_amt or "(" in raw_amt:
                    debit = abs(amt)
                else:
                    credit = amt
            if credit == 0 and debit == 0:
                continue
            transactions.append(RawTransaction(
                txn_date=dt, description=desc,
                credit=credit, debit=debit, balance=balance, raw_row=row_num
            ))
        return sorted(transactions, key=lambda x: x.txn_date)

    def _find_data_start(self, df: pd.DataFrame) -> pd.DataFrame:
        DATE_KW = ["date","debit","credit","balance","narration","description"]
        col_text = " ".join(str(c).lower() for c in df.columns)
        if any(kw in col_text for kw in DATE_KW):
            return df
        for i, row in df.iterrows():
            row_text = " ".join(str(v).lower() for v in row.values)
            if any(kw in row_text for kw in DATE_KW):
                new_df = df.iloc[i+1:].copy()
                new_df.columns = [str(df.iloc[i][c]).strip().lower() for c in df.columns]
                return new_df.reset_index(drop=True)
        return df


class PDFParser:
    def __init__(self, file_bytes: bytes, password: Optional[str] = None):
        self.file_bytes = file_bytes
        self.password   = password

    def parse(self) -> list:
        transactions = []
        try:
            import pdfplumber
            transactions = self._parse_pdfplumber()
            if transactions:
                return transactions
        except Exception as e:
            logger.warning(f"pdfplumber failed: {e}")
        try:
            import fitz
            transactions = self._parse_pymupdf()
            if transactions:
                return transactions
        except Exception as e:
            logger.warning(f"PyMuPDF failed: {e}")
        return transactions

    def _parse_pdfplumber(self) -> list:
        import pdfplumber
        transactions = []
        pdf_file = io.BytesIO(self.file_bytes)
        open_kwargs = {}
        if self.password:
            open_kwargs['password'] = self.password
        with pdfplumber.open(pdf_file, **open_kwargs) as pdf:
            for page_num, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                for table in tables:
                    rows = self._process_table(table, page_num)
                    transactions.extend(rows)
                if not tables:
                    text = page.extract_text() or ""
                    rows = self._parse_text_lines(text, page_num)
                    transactions.extend(rows)
        return self._clean_and_sort(transactions)

    def _parse_pymupdf(self) -> list:
        import fitz
        transactions = []
        doc = fitz.open(stream=self.file_bytes, filetype="pdf")
        if self.password and doc.is_encrypted:
            doc.authenticate(self.password)
        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("dict")["blocks"]
            lines = []
            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        text = " ".join(span["text"] for span in line["spans"]).strip()
                        if text:
                            lines.append(text)
            text = "\n".join(lines)
            rows = self._parse_text_lines(text, page_num)
            transactions.extend(rows)
        return self._clean_and_sort(transactions)

    def _process_table(self, table: list, page_num: int) -> list:
        if not table or len(table) < 2:
            return []
        header_row = None
        header_idx = 0
        for i, row in enumerate(table[:5]):
            row_text = " ".join(str(c or "").lower() for c in row)
            if any(kw in row_text for kw in ["date","debit","credit","balance","narration"]):
                header_row = row
                header_idx = i
                break
        if not header_row:
            return []
        col_map = self._map_columns(header_row)
        transactions = []
        for row_num, row in enumerate(table[header_idx+1:], start=header_idx+1):
            if not row or all(c is None or str(c).strip() == "" for c in row):
                continue
            txn = self._extract_from_row(row, col_map, row_num)
            if txn:
                transactions.append(txn)
        return transactions

    def _parse_text_lines(self, text: str, page_num: int) -> list:
        transactions = []
        lines = text.split('\n')
        txn_pattern = re.compile(
            r'^(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}|\d{1,2}[/\-\s][A-Za-z]{3}[/\-\s]\d{4})'
            r'\s+(.+?)\s+([\d,]+\.?\d*)\s*([\d,]+\.?\d*)?\s*([\d,]+\.?\d*)?$',
            re.MULTILINE
        )
        for row_num, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            m = txn_pattern.match(line)
            if m:
                dt = normalize_date(m.group(1))
                if dt:
                    amounts = [clean_amount(m.group(i)) for i in range(3, 6) if m.group(i)]
                    credit = debit = balance = 0.0
                    if len(amounts) == 3:
                        credit, debit, balance = amounts[0], amounts[1], amounts[2]
                    elif len(amounts) == 2:
                        credit, balance = amounts[0], amounts[1]
                    elif len(amounts) == 1:
                        credit = amounts[0]
                    transactions.append(RawTransaction(
                        txn_date=dt, description=m.group(2).strip(),
                        credit=credit, debit=debit,
                        balance=balance if balance else None,
                        raw_row=page_num * 1000 + row_num
                    ))
        return transactions

    def _map_columns(self, header: list) -> dict:
        mapping = {}
        for i, col in enumerate(header):
            if col is None:
                continue
            col_lower = str(col).lower().strip()
            if any(kw in col_lower for kw in ["date","value date","txn date"]):
                mapping["date"] = i
            elif any(kw in col_lower for kw in ["narration","description","details","particulars"]):
                mapping["description"] = i
            elif any(kw in col_lower for kw in ["credit","deposits","cr"]):
                mapping["credit"] = i
            elif any(kw in col_lower for kw in ["debit","withdrawals","dr"]):
                mapping["debit"] = i
            elif any(kw in col_lower for kw in ["balance","running balance"]):
                mapping["balance"] = i
            elif "amount" in col_lower:
                mapping["amount"] = i
        return mapping

    def _extract_from_row(self, row: list, col_map: dict, row_num: int):
        try:
            date_val = row[col_map.get("date", 0)] if "date" in col_map else None
            dt = normalize_date(str(date_val) if date_val else "")
            if not dt:
                return None
            desc_idx = col_map.get("description", 1)
            desc = str(row[desc_idx]) if desc_idx < len(row) and row[desc_idx] else "UNKNOWN"
            desc = re.sub(r'\s+', ' ', desc.strip())
            credit  = clean_amount(row[col_map["credit"]])  if "credit"  in col_map and col_map["credit"]  < len(row) else 0.0
            debit   = clean_amount(row[col_map["debit"]])   if "debit"   in col_map and col_map["debit"]   < len(row) else 0.0
            balance = clean_amount(row[col_map["balance"]]) if "balance" in col_map and col_map["balance"] < len(row) else None
            if "amount" in col_map and not credit and not debit:
                amt = clean_amount(row[col_map["amount"]])
                raw_amt = str(row[col_map["amount"]] or "")
                if "-" in raw_amt or "(" in raw_amt:
                    debit = abs(amt)
                else:
                    credit = amt
            if credit == 0 and debit == 0:
                return None
            return RawTransaction(txn_date=dt, description=desc, credit=credit, debit=debit, balance=balance, raw_row=row_num)
        except Exception as e:
            logger.debug(f"Row extract error: {e}")
            return None

    def _clean_and_sort(self, transactions: list) -> list:
        seen = set()
        unique = []
        for t in transactions:
            key = (t.txn_date.date(), round(t.credit, 2), round(t.debit, 2), t.description[:50], t.raw_row)
            if key not in seen:
                seen.add(key)
                unique.append(t)
        return sorted(unique, key=lambda x: x.txn_date)


class StatementParser:
    @staticmethod
    def parse(file_bytes: bytes, file_type: str, password: Optional[str] = None) -> list:
        file_type = file_type.lower().strip(".")
        if file_type == "pdf":
            return PDFParser(file_bytes, password).parse()
        elif file_type in ["xlsx", "xls", "csv"]:
            return ExcelCSVParser(file_bytes, file_type).parse()
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
