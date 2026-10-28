"""Helper functions for user domain."""

def normalize_email(email: str) -> str:
    return email.strip().lower()
