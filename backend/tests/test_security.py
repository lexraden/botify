from app.security import decrypt_bot_token, encrypt_bot_token


def test_token_encryption_round_trip():
    token = "1234567890:AAEhBOweik6ad9r_QXMENQknvqfy9HdKWvs"
    encrypted = encrypt_bot_token(token)
    assert encrypted != token.encode()
    assert token.encode() not in encrypted
    assert decrypt_bot_token(encrypted) == token
