from passlib.context import CryptContext

# Tells passlib to use bcrypt as the hashing algorithm
# "deprecated=auto" means if we ever switch algorithms,
# old hashes are automatically flagged for re-hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """
    Takes a plain text password and returns a bcrypt hash.
    Called once during registration — the hash is what gets stored in the DB.
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Checks if a plain text password matches a stored hash.
    Called during login — never stores or returns the plain password.
    Returns True if match, False if not.
    """
    return pwd_context.verify(plain_password, hashed_password)