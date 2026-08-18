from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
import bcrypt as _bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db, User, UserRole

SECRET_KEY = "procurement-system-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

security = HTTPBearer(auto_error=False)


def verify_password(plain_password, hashed_password):
    if isinstance(plain_password, str):
        plain_password = plain_password.encode("utf-8")
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode("utf-8")
    return _bcrypt.checkpw(plain_password, hashed_password)


def get_password_hash(password):
    if isinstance(password, str):
        password = password.encode("utf-8")
    salt = _bcrypt.gensalt()
    return _bcrypt.hashpw(password, salt).decode("utf-8")


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    if credentials is None:
        return None
    try:
        payload = jwt.decode(
            credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None
    user = db.query(User).filter(User.username == username).first()
    return user


def require_admin(user: User = Depends(get_current_user)):
    if user is None or user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def require_editor(user: User = Depends(get_current_user)):
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    if user.role not in [UserRole.ADMIN.value, UserRole.EDITOR.value]:
        raise HTTPException(status_code=403, detail="没有编辑权限")
    return user