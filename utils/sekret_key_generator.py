import os
import base64

# Генерация 64-байтного секрета
secret_key = base64.b64encode(os.urandom(64)).decode('utf-8')
print(f"SECRET_KEY = '{secret_key}'")