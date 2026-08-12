from datetime import date

from app.main import announcement_message, business_days, parse_leave_command


def test_business_days_excludes_weekend():
    assert business_days(date(2026, 8, 14), date(2026, 8, 17)) == 2


def test_parse_leave_command():
    assert parse_leave_command("ขอลา พักร้อน 2026-08-20 2026-08-21 ไปต่างจังหวัด") == (
        "vacation",
        date(2026, 8, 20),
        date(2026, 8, 21),
        "ไปต่างจังหวัด",
    )


def test_parse_leave_rejects_reverse_dates():
    assert parse_leave_command("ขอลา ป่วย 2026-08-21 2026-08-20") is None


def test_announcement_is_flex_card():
    message = announcement_message("วันหยุดบริษัท", "บริษัทหยุดวันที่ 20 สิงหาคม")
    assert message["type"] == "flex"
    assert message["contents"]["type"] == "bubble"
    assert message["contents"]["body"]["contents"][0]["text"] == "วันหยุดบริษัท"
