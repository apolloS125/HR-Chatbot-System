import re


def mask_text(text: str) -> str:
    # ponytail: common identifiers only; add entity detection before importing personnel records.
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
    text = re.sub(r"(?<!\d)(?:\+66|0)[\d -]{8,12}(?!\d)", "[PHONE]", text)
    text = re.sub(r"(?<!\d)\d{13}(?!\d)", "[ID]", text)
    # shortcut: mask titled/labeled names; unmarked names still need entity detection.
    text = re.sub(
        r"(?:นางสาว|นาย|นาง|คุณ)\s+[ก-๙]+(?:\s+[ก-๙]+)?",
        "[NAME]",
        text,
    )
    text = re.sub(
        r"\b(?:Mr\.?|Mrs\.?|Ms\.?|Dr\.?)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?",
        "[NAME]",
        text,
    )
    text = re.sub(
        r"(?:ชื่อ(?:-นามสกุล)?|full name|name)\s*[:：]\s*[^\n,;]+",
        "[NAME]",
        text,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\b(?:E\d{3,}|U[0-9a-f]{32})\b", "[EMPLOYEE]", text, flags=re.IGNORECASE)
