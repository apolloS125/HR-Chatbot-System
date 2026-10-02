import re


def mask_text(text: str) -> str:
    # ponytail: common identifiers only; add entity detection before importing personnel records.
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
    text = re.sub(r"(?<!\d)(?:\+66|0)[\d -]{8,12}(?!\d)", "[PHONE]", text)
    text = re.sub(r"(?<!\d)\d{13}(?!\d)", "[ID]", text)
    return re.sub(r"\b(?:E\d{3,}|U[0-9a-f]{32})\b", "[EMPLOYEE]", text, flags=re.IGNORECASE)
