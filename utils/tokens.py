# File: CodeQuizHub/utils/tokens.py
from secrets import token_urlsafe

def generate_token():
    """Generates a secure URL-safe token."""
    return token_urlsafe(32)