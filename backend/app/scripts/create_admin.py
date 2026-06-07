import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole


DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123456"


def ensure_admin_role(db: Session) -> Role:
    role = db.scalar(select(Role).where(Role.code == "admin"))
    if role is None:
        role = Role(
            code="admin",
            name="管理员",
            description="拥有系统全部权限",
            is_system=True,
        )
        db.add(role)
        db.flush()
    return role


def ensure_admin_user(db: Session, username: str, password: str) -> User:
    user = db.scalar(select(User).where(User.username == username))
    password_hash = get_password_hash(password)

    if user is None:
        user = User(
            username=username,
            password_hash=password_hash,
            display_name="系统管理员",
            is_active=True,
            is_superuser=True,
        )
        db.add(user)
        db.flush()
    else:
        user.password_hash = password_hash
        user.is_active = True
        user.is_superuser = True
        db.flush()

    return user


def ensure_user_role(db: Session, user: User, role: Role) -> None:
    exists = db.scalar(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role_id == role.id,
        )
    )
    if exists is None:
        db.add(UserRole(user_id=user.id, role_id=role.id))


def create_admin() -> None:
    username = os.getenv("ADMIN_USERNAME", DEFAULT_ADMIN_USERNAME)
    password = os.getenv("ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)

    with SessionLocal() as db:
        role = ensure_admin_role(db)
        user = ensure_admin_user(db, username, password)
        ensure_user_role(db, user, role)
        db.commit()

    print(f"Created or updated admin user: {username}")


if __name__ == "__main__":
    create_admin()
