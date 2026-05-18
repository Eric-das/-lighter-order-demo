"""File loaders: extract plain text from PDF / Excel / CSV / TXT uploads."""
import io

import pandas as pd


def load_text_from_file(file) -> str:
    """Streamlit UploadedFile -> plain text.

    Supported: .txt, .csv, .xlsx, .xls, .pdf
    """
    name = (file.name or "").lower()
    data = file.getvalue()

    if name.endswith(".txt"):
        return _decode_bytes(data)

    if name.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(data))
        return _df_to_text(df)

    if name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(data))
        return _df_to_text(df)

    if name.endswith(".pdf"):
        return _extract_pdf_text(io.BytesIO(data))

    raise ValueError(f"Unsupported file format: {file.name}")


def _decode_bytes(data: bytes) -> str:
    """Best-effort decoding for txt files (UTF-8 first, then GBK)."""
    for enc in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _df_to_text(df: pd.DataFrame) -> str:
    """DataFrame -> aligned text table (header + rows)."""
    return df.to_string(index=False)


def _extract_pdf_text(stream: io.BytesIO) -> str:
    """PDF stream -> text. Requires pdfplumber."""
    try:
        import pdfplumber
    except ImportError as e:
        raise RuntimeError(
            "PDF parsing requires pdfplumber. Run: pip install pdfplumber"
        ) from e

    pages = []
    with pdfplumber.open(stream) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages)
