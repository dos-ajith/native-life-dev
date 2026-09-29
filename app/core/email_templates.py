from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from string import Template

_EMAIL_SHELL_HTML_TEMPLATE = Template("""<!DOCTYPE html PUBLIC
  "-//W3C//DTD XHTML 1.0 Transitional//EN"
  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="en">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="color-scheme" content="light" />
<meta name="supported-color-schemes" content="light" />
<meta name="x-apple-disable-message-reformatting" />
<meta name="format-detection" content="telephone=no, date=no, address=no, email=no" />
<title>$title</title>
<style>
body, table, td { -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }
table, td { mso-table-lspace: 0pt; mso-table-rspace: 0pt; }
img { border: 0; line-height: 100%; outline: none; text-decoration: none; }
@media (max-width: 620px) {
  .container { width: 100% !important; }
  .content-padding {
    padding-left: 24px !important;
    padding-right: 24px !important;
  }
  .otp-code { font-size: 28px !important; letter-spacing: 6px !important; }
}
</style>
</head>
<body style="margin:0; padding:0; background-color:#F5F7F5;" bgcolor="#F5F7F5">
<table
  role="presentation" border="0" width="100%" cellpadding="0" cellspacing="0"
  bgcolor="#F5F7F5" style="background-color:#F5F7F5; padding:32px 16px;"
>
<tr>
<td align="center">
<!--[if mso]>
<table role="presentation" align="center" border="0" cellpadding="0" cellspacing="0" width="600">
<tr>
<td>
<![endif]-->
<table
  role="presentation" class="container" border="0" width="600"
  cellpadding="0" cellspacing="0" bgcolor="#FFFFFF" align="center"
  style="max-width:600px; width:100%; background-color:#FFFFFF;
    border:1px solid #E5E7EB; border-radius:12px;"
>
<tr>
<td
  class="content-padding"
  style="padding:36px 40px 28px 40px; text-align:center;
    border-bottom:1px solid #EEF2F0;"
>
<span
  style="font-family: Arial, Helvetica, sans-serif; font-size:22px;
    font-weight:700; color:#0F2E1D;"
>Native <span style="color:#1B7F4C;">Life</span></span>
</td>
</tr>
<tr>
<td class="content-padding" style="padding:40px 40px 8px 40px; text-align:center;">
<h1
  style="margin:0; font-family: Arial, Helvetica, sans-serif; font-size:24px;
    line-height:32px; color:#111827;"
>$heading</h1>
</td>
</tr>
$body_html
<tr>
<td
  class="content-padding"
  style="padding:28px 40px 32px 40px; border-top:1px solid #EEF2F0; text-align:center;"
>
<p
  style="margin:0 0 8px 0; font-family: Arial, Helvetica, sans-serif; font-size:13px;
    font-weight:600; color:#111827;"
>$app_name</p>
<p
  style="margin:0 0 10px 0; font-family: Arial, Helvetica, sans-serif; font-size:12px;
    color:#6B7280;"
>$support_line</p>
$legal_line_html
<p style="margin:0; font-family: Arial, Helvetica, sans-serif; font-size:11px; color:#9CA3AF;">
&copy; $year Native Life. All rights reserved.</p>
</td>
</tr>
</table>
<!--[if mso]>
</td>
</tr>
</table>
<![endif]-->
</td>
</tr>
</table>
</body>
</html>""")

_VERIFICATION_OTP_BODY_HTML_TEMPLATE = Template("""
<tr>
<td class="content-padding" style="padding:8px 40px 32px 40px; text-align:center;">
<p
  style="margin:0; font-family: Arial, Helvetica, sans-serif; font-size:15px;
    line-height:22px; color:#6B7280;"
>Use the verification code below to verify your $app_name account.</p>
</td>
</tr>
<tr>
<td class="content-padding" style="padding:0 40px 32px 40px;" align="center">
<table
  role="presentation" border="0" cellpadding="0" cellspacing="0" bgcolor="#EAF7EF"
  style="background-color:#EAF7EF; border:1px solid #BFE8D0; border-radius:10px;"
>
<tr>
<td style="padding:22px 40px;" align="center">
<span
  class="otp-code"
  style="font-family: 'Courier New', Courier, monospace; font-size:34px;
    font-weight:700; letter-spacing:10px; color:#0F2E1D;"
>$otp</span>
</td>
</tr>
</table>
</td>
</tr>
<tr>
<td class="content-padding" style="padding:0 40px 32px 40px; text-align:center;">
<p
  style="margin:0; font-family: Arial, Helvetica, sans-serif; font-size:14px;
    color:#6B7280;"
>This code will expire in
<strong style="color:#111827;">$expire_minutes minutes</strong>.</p>
</td>
</tr>
<tr>
<td class="content-padding" style="padding:0 40px 40px 40px;">
<table
  role="presentation" border="0" width="100%" cellpadding="0" cellspacing="0"
  bgcolor="#F5F7F5" style="background-color:#F5F7F5; border-radius:8px;"
>
<tr>
<td
  style="padding:16px 20px; font-family: Arial, Helvetica, sans-serif; font-size:13px;
    line-height:19px; color:#4B5563;"
>If you didn't request this code, you can safely ignore this email.</td>
</tr>
</table>
</td>
</tr>""")


@dataclass(frozen=True)
class EmailContent:
    subject: str
    text_body: str
    html_body: str


def render_transactional_email(
    subject: str,
    heading: str,
    body_html: str,
    body_text: str,
    app_name: str,
    support_url: str | None,
    privacy_policy_url: str | None,
    terms_of_service_url: str | None,
) -> EmailContent:
    text_body = f"{heading}\n\n{body_text}\n\n{app_name}"

    html_body = _EMAIL_SHELL_HTML_TEMPLATE.substitute(
        title=escape(subject),
        heading=escape(heading),
        body_html=body_html,
        app_name=escape(app_name),
        support_line=_build_support_line(support_url),
        legal_line_html=_build_legal_line_html(privacy_policy_url, terms_of_service_url),
        year=datetime.now(UTC).year,
    )

    return EmailContent(subject=subject, text_body=text_body, html_body=html_body)


def render_verification_otp_email(
    app_name: str,
    otp: str,
    expire_minutes: int,
    support_url: str | None,
    privacy_policy_url: str | None,
    terms_of_service_url: str | None,
) -> EmailContent:
    escaped_app_name = escape(app_name)
    escaped_otp = escape(otp)

    body_html = _VERIFICATION_OTP_BODY_HTML_TEMPLATE.substitute(
        app_name=escaped_app_name,
        otp=escaped_otp,
        expire_minutes=expire_minutes,
    )

    body_text = (
        f"Use the verification code below to verify your {app_name} account.\n\n"
        f"Your verification code is: {otp}\n"
        f"This code will expire in {expire_minutes} minutes.\n\n"
        f"If you didn't request this code, you can safely ignore this email."
    )

    return render_transactional_email(
        subject=f"Your {app_name} verification code",
        heading="Verify your email",
        body_html=body_html,
        body_text=body_text,
        app_name=app_name,
        support_url=support_url,
        privacy_policy_url=privacy_policy_url,
        terms_of_service_url=terms_of_service_url,
    )


def _build_support_line(support_url: str | None) -> str:
    if not support_url:
        return "Need help? Contact our support team."
    return (
        f'Need help? Contact our <a href="{support_url}" '
        f'style="color:#1B7F4C; text-decoration:underline;">support team</a>.'
    )


def _build_legal_line_html(privacy_policy_url: str | None, terms_of_service_url: str | None) -> str:
    legal_links = []
    if privacy_policy_url:
        legal_links.append(
            f'<a href="{privacy_policy_url}" style="color:#6B7280; text-decoration:underline;">'
            f"Privacy Policy</a>"
        )
    if terms_of_service_url:
        legal_links.append(
            f'<a href="{terms_of_service_url}" style="color:#6B7280; text-decoration:underline;">'
            f"Terms of Service</a>"
        )
    if not legal_links:
        return ""
    return (
        f'<p style="margin:0 0 14px 0; font-family: Arial, Helvetica, sans-serif; '
        f'font-size:12px; color:#9CA3AF;">{" | ".join(legal_links)}</p>'
    )
