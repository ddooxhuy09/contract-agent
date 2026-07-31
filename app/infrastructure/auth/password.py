from passlib.context import CryptContext

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


class BcryptPasswordHasher:
    def hash(self, password: str) -> str:
        return _pwd.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        return _pwd.verify(password, password_hash)
