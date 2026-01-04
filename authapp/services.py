def send_sms_dummy(mobile, code):
    """Simulate sending OTP SMS (no real SMS)."""
    # In production replace this with real SMS provider integration.
    print(f"[DEV] Sending OTP {code} to {mobile}")
    return True
