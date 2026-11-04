import os
import uuid

TEST_SCHEMA = f"test_{uuid.uuid4().hex[:12]}"

os.environ.setdefault("OTP_HMAC_SECRET_KEY", "test-only-otp-hmac-secret-key-0123456789abcdef")
os.environ["APP_ENV"] = "test"
os.environ["SMS_PROVIDER"] = "disabled"
os.environ["MANDRILL_ENABLED"] = "false"
os.environ["SMTP_HOST"] = ""
os.environ["PGOPTIONS"] = f"-c search_path={TEST_SCHEMA},public"
