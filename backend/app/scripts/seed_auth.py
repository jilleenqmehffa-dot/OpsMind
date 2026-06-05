from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission


PERMISSIONS = [
    {
        "code": "wiki:read",
        "name": "查看 Wiki",
        "description": "查看 Wiki 页面和文档内容",
    },
    {
        "code": "wiki:create",
        "name": "创建 Wiki",
        "description": "创建新的 Wiki 页面和文档",
    },
    {
        "code": "wiki:update",
        "name": "编辑 Wiki",
        "description": "编辑已有 Wiki 页面和文档",
    },
    {
        "code": "wiki:delete",
        "name": "删除 Wiki",
        "description": "删除 Wiki 页面和文档",
    },
    {
        "code": "user:manage",
        "name": "管理用户",
        "description": "创建、禁用和调整用户角色",
    },
    {
        "code": "system:config",
        "name": "修改系统配置",
        "description": "修改系统级配置项",
    },
]

ROLES = [
    {
        "code": "admin",
        "name": "管理员",
        "description": "拥有系统全部权限",
        "permission_codes": [
            "wiki:read",
            "wiki:create",
            "wiki:update",
            "wiki:delete",
            "user:manage",
            "system:config",
        ],
    },
    {
        "code": "user",
        "name": "普通用户",
        "description": "可以查看、创建和编辑 Wiki",
        "permission_codes": [
            "wiki:read",
            "wiki:create",
            "wiki:update",
        ],
    },
]


def get_or_create_permission(db: Session, data: dict[str, str]) -> Permission:
    permission = db.scalar(select(Permission).where(Permission.code == data["code"]))
    if permission is not None:
        permission.name = data["name"]
        permission.description = data["description"]
        return permission

    permission = Permission(**data)
    db.add(permission)
    return permission


def get_or_create_role(db: Session, data: dict[str, object]) -> Role:
    role = db.scalar(select(Role).where(Role.code == data["code"]))
    if role is not None:
        role.name = str(data["name"])
        role.description = str(data["description"])
        role.is_system = True
        return role

    role = Role(
        code=str(data["code"]),
        name=str(data["name"]),
        description=str(data["description"]),
        is_system=True,
    )
    db.add(role)
    return role


def ensure_role_permission(db: Session, role: Role, permission: Permission) -> None:
    exists = db.scalar(
        select(RolePermission).where(
            RolePermission.role_id == role.id,
            RolePermission.permission_id == permission.id,
        )
    )
    if exists is None:
        db.add(RolePermission(role_id=role.id, permission_id=permission.id))


def seed_auth() -> None:
    with SessionLocal() as db:
        permissions_by_code = {
            item["code"]: get_or_create_permission(db, item)
            for item in PERMISSIONS
        }
        roles_by_code = {
            str(item["code"]): get_or_create_role(db, item)
            for item in ROLES
        }
        db.flush()

        for role_data in ROLES:
            role = roles_by_code[str(role_data["code"])]
            for permission_code in role_data["permission_codes"]:
                permission = permissions_by_code[str(permission_code)]
                ensure_role_permission(db, role, permission)

        db.commit()

    print("Seeded auth roles and permissions.")


if __name__ == "__main__":
    seed_auth()
