import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole


DEFAULT_DEMO_USERNAME = "opsuser"
DEFAULT_DEMO_PASSWORD = "opsuser123456"


def ensure_demo_user(db: Session, username: str, password: str) -> User:
    user = db.scalar(select(User).where(User.username == username))
    password_hash = get_password_hash(password)

    if user is None:
        user = User(
            username=username,
            password_hash=password_hash,
            display_name="运维用户",
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
        db.flush()
    else:
        user.password_hash = password_hash
        user.is_active = True
        user.is_superuser = False
        db.flush()

    return user


def ensure_user_role(db: Session, user: User) -> None:
    role = db.scalar(select(Role).where(Role.code == "user"))
    if role is None:
        raise RuntimeError("Role 'user' does not exist. Run app.scripts.seed_auth first.")

    exists = db.scalar(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role_id == role.id,
        )
    )
    if exists is None:
        db.add(UserRole(user_id=user.id, role_id=role.id))


def create_demo_user() -> None:
    username = os.getenv("DEMO_USERNAME", DEFAULT_DEMO_USERNAME)
    password = os.getenv("DEMO_PASSWORD", DEFAULT_DEMO_PASSWORD)

    with SessionLocal() as db:
        user = ensure_demo_user(db, username, password)
        ensure_user_role(db, user)
        db.commit()

    print(f"Created or updated demo user: {username}")


if __name__ == "__main__":
    create_demo_user()
