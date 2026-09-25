#!/usr/bin/env python3
"""Generate a Fernet key (32 random bytes url-safe base64-encoded)."""
import os
import base64
key = base64.urlsafe_b64encode(os.urandom(32))
print(key.decode('utf-8'))