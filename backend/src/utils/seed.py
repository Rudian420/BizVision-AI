"""
BizVision AI — Database Seeder

Idempotently creates the tables and a default admin + analyst account for
local development. Safe to run repeatedly (`make seed`).

    python -m src.utils.seed
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

# Import all models so metadata is fully populated before create_all.
import src.models  # noqa: F401
from src.core.database import AsyncSessionLocal, Base, engine
from src.core.security import hash_password
from src.models.user import User, UserRole

_SEED_USERS = [
    {
        "email": "admin@bizvision.ai",
        "password": "admin12345",
        "full_name": "BizVision Admin",
        "company_name": "BizVision AI",
        "role": UserRole.ADMIN,
        "is_verified": True,
    },
    {
        "email": "analyst@bizvision.ai",
        "password": "analyst12345",
        "full_name": "Demo Analyst",
        "company_name": "Acme SME Ltd.",
        "role": UserRole.ANALYST,
        "is_verified": True,
    },
]


async def _seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    created = 0
    async with AsyncSessionLocal() as session:
        for spec in _SEED_USERS:
            existing = await session.execute(select(User).where(User.email == spec["email"]))
            if existing.scalar_one_or_none() is not None:
                continue
            session.add(
                User(
                    email=spec["email"],
                    hashed_password=hash_password(spec["password"]),
                    full_name=spec["full_name"],
                    company_name=spec["company_name"],
                    role=spec["role"],
                    is_verified=spec["is_verified"],
                )
            )
            created += 1
        await session.commit()

    await engine.dispose()
    print(
        f"[seed] Done. Created {created} new user(s); {len(_SEED_USERS) - created} already existed."
    )
    print("[seed] Login: admin@bizvision.ai / admin12345")


def main() -> None:
    asyncio.run(_seed())


if __name__ == "__main__":
    main()
