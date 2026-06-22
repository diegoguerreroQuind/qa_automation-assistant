"""
Role-Based Access Control (RBAC) dependency for FastAPI routes.

Usage:
    @router.delete("/{id}", dependencies=[Depends(require_role(UserRole.admin))])
    async def delete_resource(...):
        ...

    # Or inject the user object:
    @router.delete("/{id}")
    async def delete_resource(
        current_user: User = Depends(require_role(UserRole.admin, UserRole.qa))
    ):
        ...
"""
from fastapi import Depends, HTTPException, status

from backend.models.db import User, UserRole
from backend.security.jwt import get_current_user


def require_role(*roles: UserRole):
    """
    FastAPI dependency factory.

    Returns a dependency that resolves to the current User if their role is
    in the allowed list, or raises HTTP 403 Forbidden otherwise.

    Example:
        Depends(require_role(UserRole.admin))
        Depends(require_role(UserRole.admin, UserRole.qa))
    """
    async def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            allowed = [r.value for r in roles]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Se requiere uno de los roles: {allowed}",
            )
        return current_user

    return _checker
