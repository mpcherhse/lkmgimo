"""Пароли и секреты.
- Пароли: Argon2id (argon2-cffi), в базе только хэш. Проверка надёжности — zxcvbn плюс русские слова и «набрано в другой раскладке».
- Токены сеансов, ссылки календаря, пароли приложений: случайные значения из secrets, в базе — SHA-256 (для 256-битных
  случайных строк медленный хэш не нужен: перебор невозможен).
- Секрет TOTP нужно уметь прочитать, поэтому он зашифрован AES-GCM ключом сервера (LK_SECRET_KEY)."""
import base64
import hashlib
import os
import secrets
import unicodedata
from functools import lru_cache
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError, InvalidHashError

from . import config

PH = PasswordHasher()   # Argon2id, параметры по умолчанию RFC 9106 (low-memory)
PASSWORD_MIN, PASSWORD_MAX = 12, 128
STRENGTH_MIN = 3
RESOURCES = Path(__file__).resolve().parent / "resources"
# хэш для несуществующего логина: время ответа одинаковое, перебором логинов не узнать, кто зарегистрирован
DUMMY_HASH = PH.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return PH.hash(password)


def verify_password(stored: str, password: str) -> bool:
    try:
        return PH.verify(stored, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError, ValueError):
        return False


def new_token(nbytes=32) -> str:
    return secrets.token_urlsafe(nbytes)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def public_id() -> str:
    return secrets.token_urlsafe(9)


# пароль приложения для календаря: 16 символов без похожих (0/O, 1/l/I), группы по 4 — удобно набирать на телефоне
APP_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def app_password() -> str:
    chars = "".join(secrets.choice(APP_ALPHABET) for _ in range(16))
    return "-".join(chars[i:i + 4] for i in range(0, 16, 4))


# ---------- шифрование секрета TOTP ----------
def encrypt(plain: str) -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    ct = AESGCM(config.secret_key()).encrypt(nonce, plain.encode(), b"totp")
    return "v1:" + base64.b64encode(nonce + ct).decode()


def decrypt(token: str) -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if not token.startswith("v1:"):
        raise ValueError("unknown secret format")
    raw = base64.b64decode(token[3:])
    return AESGCM(config.secret_key()).decrypt(raw[:12], raw[12:], b"totp").decode()


# ---------- правила нового пароля ----------
RU_WORDS = ["пароль", "парольпароль", "привет", "любовь", "москва", "россия", "студент", "студентка", "деканат", "мгимо", "mgimo",
            "университет", "учеба", "сессия", "зачет", "экзамен", "зима", "лето", "весна", "осень", "солнце", "котик", "собака",
            "йцукен", "йцукенгшщзхъ", "фывапролджэ", "ячсмитьбю", "qwerty", "parol", "privet", "moskva", "rossiya", "student"]
_LAT = "qwertyuiop[]asdfghjkl;'zxcvbnm,./`QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<>?~"
_CYR = "йцукенгшщзхъфывапролджэячсмитьбю.ёЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,Ё"
TO_LAT = str.maketrans(_CYR, _LAT)
TO_CYR = str.maketrans(_LAT, _CYR)


@lru_cache(maxsize=1)
def _common():
    p = RESOURCES / "common-passwords.txt"
    if not p.exists():
        return frozenset()
    return frozenset(x.strip() for x in p.read_text("utf-8", "ignore").splitlines() if x.strip())


def _score(pw, inputs):
    from zxcvbn import zxcvbn
    head = pw[:72]
    variants = {head, head.translate(TO_LAT), head.translate(TO_CYR)}
    return min(zxcvbn(v, user_inputs=inputs)["score"] for v in variants if v)


def strength_label(score):
    return "надёжный" if score >= STRENGTH_MIN else "средний" if score == 2 else "слабый"


def check_password(pw, login="", names=()):
    """-> {problems: [...], score: 0–4, strength}. Пустой problems — пароль подходит"""
    problems = []
    if not isinstance(pw, str):
        return {"problems": ["Пароль должен быть строкой"], "score": 0, "strength": "слабый"}
    if len(pw) < PASSWORD_MIN:
        problems.append(f"Пароль должен быть не короче {PASSWORD_MIN} символов")
    if len(pw) > PASSWORD_MAX:
        problems.append(f"Пароль должен быть не длиннее {PASSWORD_MAX} символов")
    if any(ch.isspace() or unicodedata.category(ch).startswith(("Z", "C")) for ch in pw):
        problems.append("В пароле не должно быть пробелов и служебных символов")
    if unicodedata.normalize("NFKC", pw) != pw:
        problems.append("В пароле есть символы, которые на другом устройстве наберутся иначе")
    inputs = [x for x in {login, *[n.lower() for n in names if n]} if x and len(x) >= 3] + RU_WORDS
    score = 0
    if pw and len(pw) <= PASSWORD_MAX:
        score = _score(pw, inputs)
        key = unicodedata.normalize("NFKC", pw).casefold()
        if key in _common() or key.translate(TO_LAT) in _common():
            problems.append("Этот пароль есть в списках самых частых паролей")
            score = min(score, 1)
        elif login and len(login) >= 4 and login.lower() in key:
            problems.append("Пароль не должен содержать логин")
            score = min(score, 2)
        if score < STRENGTH_MIN and not problems:
            problems.append("Пароль слишком простой: возьмите фразу из трёх-четырёх слов, цифры и знаки внутри, а не в конце")
    return {"problems": problems, "score": score, "strength": strength_label(score)}
