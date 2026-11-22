"""Служебные команды:
  python -m app.cli secret-key        — новый LK_SECRET_KEY (32 случайных байта, base64)
  python -m app.cli totp-secret       — секрет TOTP для демо-сотрудника (LK_DEMO_TOTP_SECRET)
  python -m app.cli migrate           — применить миграции
  python -m app.cli seed [--reset]    — заполнить базу вымышленными данными (--reset: стереть схему перед этим)
"""
import base64
import os
import sys


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "secret-key":
        print(base64.b64encode(os.urandom(32)).decode())
    elif cmd == "totp-secret":
        import pyotp
        print(pyotp.random_base32(32))
    elif cmd in ("migrate", "seed"):
        from . import seed
        from .db import direct, migrate
        with direct() as conn:
            if cmd == "seed" and "--reset" in argv:
                conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
            migrate(conn)
            if cmd == "seed":
                seed.run(conn)
        print("готово")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
