"""Create an admin user interactively.

Usage (from backend/): uv run python -m scripts.create_admin
"""

import sys
from getpass import getpass

from pydantic import ValidationError

from app.core.db import SessionLocal
from app.core.errors import AppError, translate_integrity_errors
from app.core.security import hash_password
from app.models import User
from app.modules.auth.schemas import RegisterRequest
from app.modules.users.models import UserRole


def main() -> None:
    try:
        data = RegisterRequest(
            email=input("Email: "),
            full_name=input("Full name: "),
            password=getpass("Password (8-128 characters): "),
        )
    except ValidationError as exc:
        # Print field and reason only: the default message would echo the password back.
        problems = "; ".join(f"{error['loc'][0]}: {error['msg']}" for error in exc.errors())
        sys.exit(f"Invalid input: {problems}")

    admin = User(
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        role=UserRole.ADMIN,
    )
    with SessionLocal() as db:
        db.add(admin)
        try:
            with translate_integrity_errors(db):
                db.commit()
        except AppError as exc:
            sys.exit(exc.message)
    print(f"Admin created: {admin.email}")


if __name__ == "__main__":
    main()
