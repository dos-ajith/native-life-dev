def render_phone_otp_sms(app_name: str, otp: str, expire_minutes: int) -> str:
    return (
        f"{otp} is your {app_name} verification code. "
        f"It expires in {expire_minutes} minutes. Do not share it with anyone."
    )
