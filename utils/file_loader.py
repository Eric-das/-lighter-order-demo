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
            # overprint fake-bold PDFs draw each glyph several times with a
            # sub-point offset; dedupe_chars merges those duplicates
            try:
                page = page.dedupe_chars(tolerance=2)
            except Exception:
                pass  # keep raw page if dedupe is unavailable/fails
            pages.append(page.extract_text() or "")
    return _collapse_overprint_runs("\n".join(pages))


def _collapse_overprint_runs(text: str) -> str:
    """Fallback for overprint PDFs that dedupe_chars misses.

    Such extractions repeat EVERY glyph a fixed k times in a row
    ("宁宁宁宁波波波波" / "2222000022225555"). Detect a dominant repeat
    factor k over the whole document; only when the pattern is pervasive,
    collapse each run whose length is a multiple of k.
    """
    import re
    from collections import Counter

    runs = [(ch, len(m.group(0)))
            for m in re.finditer(r"(.)\1*", text, flags=re.DOTALL)
            for ch in [m.group(1)]]
    multi = [n for ch, n in runs if n > 1 and not ch.isspace()]
    if len(multi) < 20:
        return text
    k = Counter(multi).most_common(1)[0][0]
    if k < 2:
        return text
    # pervasive = most repeated glyphs share the same factor
    if sum(1 for n in multi if n % k == 0) < 0.8 * len(multi):
        return text
    out = []
    for ch, n in runs:
        if not ch.isspace() and n % k == 0:
            out.append(ch * (n // k))
        else:
            out.append(ch * n)
    return "".join(out)
