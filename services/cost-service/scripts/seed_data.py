"""
CloudPulse AI - Demo data seeding script.

Creates a demo tenant, demo accounts, and realistic cost history that can be
used immediately in the UI and ML endpoints.
"""
import argparse
import asyncio
import re
import sys
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.models import Base, CloudAccount, CostRecord, Organization, User  # noqa: E402
from app.services.demo_seed import (  # noqa: E402
    DEFAULT_DEMO_ACCOUNT_ID,
    DEFAULT_DEMO_ACCOUNT_NAME,
    DEFAULT_DEMO_ACCOUNT_PROFILES,
    DEFAULT_DEMO_SEED,
    DEFAULT_LOOKBACK_DAYS,
    DemoAccountProfile,
    build_demo_cost_records,
    build_demo_credentials,
)

settings = get_settings()

DEFAULT_DEMO_EMAIL = "demo@cloudpulse.local"
DEFAULT_DEMO_PASSWORD = "DemoPass123!"
DEFAULT_DEMO_ORG = "CloudPulse Demo"


def slugify(value: str) -> str:
    """Create a stable slug for the demo organization."""
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "cloudpulse-demo"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for demo data seeding."""
    parser = argparse.ArgumentParser(description="Seed demo data for CloudPulse AI")
    parser.add_argument("--reset", action="store_true", help="Delete and recreate demo data")
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help=f"Number of daily history points to generate (default: {DEFAULT_LOOKBACK_DAYS})",
    )
    parser.add_argument("--email", default=DEFAULT_DEMO_EMAIL, help="Demo admin email")
    parser.add_argument("--password", default=DEFAULT_DEMO_PASSWORD, help="Demo admin password")
    parser.add_argument("--org", default=DEFAULT_DEMO_ORG, help="Demo organization name")
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_DEMO_SEED,
        help=f"Deterministic seed for demo record generation (default: {DEFAULT_DEMO_SEED})",
    )
    return parser.parse_args()


async def ensure_schema() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Ensure database schema exists and return a session factory."""
    engine = create_async_engine(str(settings.database_url), echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def find_demo_org(session: AsyncSession, org_slug: str) -> Organization | None:
    """Fetch the demo organization by slug."""
    result = await session.execute(select(Organization).where(Organization.slug == org_slug))
    return result.scalar_one_or_none()


async def count_existing_demo_records(session: AsyncSession, org_id: str) -> tuple[int, int]:
    """Count existing demo accounts and records for the target organization."""
    accounts_result = await session.execute(
        select(CloudAccount).where(
            CloudAccount.organization_id == org_id,
            CloudAccount.provider == "demo",
        )
    )
    accounts = accounts_result.scalars().all()

    if not accounts:
        return 0, 0

    account_ids = [account.id for account in accounts]
    record_count = await session.scalar(
        select(func.count(CostRecord.id)).where(CostRecord.cloud_account_id.in_(account_ids))
    ) or 0
    return len(accounts), int(record_count)


async def upsert_demo_account(
    session: AsyncSession,
    organization_id: str,
    profile: DemoAccountProfile,
    seed: int,
    days: int,
) -> int:
    """Create or refresh a deterministic demo account and its seeded records."""
    result = await session.execute(
        select(CloudAccount).where(
            CloudAccount.organization_id == organization_id,
            CloudAccount.account_id == profile.account_id,
        )
    )
    demo_account = result.scalar_one_or_none()

    if demo_account is None:
        demo_account = CloudAccount(
            organization_id=organization_id,
            provider="demo",
            account_id=profile.account_id,
            account_name=profile.account_name,
            is_active=True,
            credentials=build_demo_credentials(profile, seed),
        )
        session.add(demo_account)
        await session.flush()
    else:
        demo_account.account_name = profile.account_name
        demo_account.provider = "demo"
        demo_account.is_active = True
        demo_account.credentials = build_demo_credentials(profile, seed)
        await session.execute(
            delete(CostRecord).where(CostRecord.cloud_account_id == demo_account.id)
        )

    records = await build_demo_cost_records(
        demo_account.id,
        days,
        profile=profile,
        seed=seed,
    )
    session.add_all(records)
    return len(records)


async def seed_demo_data(args: argparse.Namespace) -> None:
    """Seed the demo organization, login, and preset cloud accounts."""
    engine, session_factory = await ensure_schema()
    org_slug = slugify(args.org)

    async with session_factory() as session:
        demo_org = await find_demo_org(session, org_slug)
        if demo_org and args.reset:
            await session.delete(demo_org)
            await session.commit()
            demo_org = None

        if demo_org and not args.reset:
            existing_user_result = await session.execute(
                select(User).where(User.organization_id == demo_org.id, User.email == args.email)
            )
            existing_user = existing_user_result.scalar_one_or_none()
            existing_accounts, existing_records = await count_existing_demo_records(
                session,
                demo_org.id,
            )

            if (
                existing_user
                and existing_accounts >= len(DEFAULT_DEMO_ACCOUNT_PROFILES)
                and existing_records > 0
            ):
                print("Demo data already exists.")
                print(f"Email:    {args.email}")
                print(f"Password: {args.password}")
                print(f"Accounts: {existing_accounts}")
                print(f"Records:  {existing_records}")
                return

        existing_user_result = await session.execute(select(User).where(User.email == args.email))
        existing_user = existing_user_result.scalar_one_or_none()
        if existing_user and (not demo_org or existing_user.organization_id != demo_org.id):
            raise RuntimeError(
                f"User {args.email} already exists outside the demo tenant. "
                "Use a different email or rerun with --email."
            )

        if demo_org is None:
            demo_org = Organization(name=args.org, slug=org_slug)
            session.add(demo_org)
            await session.flush()

        if existing_user is None:
            existing_user = User(
                organization_id=demo_org.id,
                email=args.email,
                hashed_password=get_password_hash(args.password),
                full_name="Demo Admin",
                role="admin",
            )
            session.add(existing_user)
            await session.flush()

        total_records = 0
        seeded_accounts = 0
        for profile in DEFAULT_DEMO_ACCOUNT_PROFILES:
            total_records += await upsert_demo_account(
                session,
                demo_org.id,
                profile,
                args.seed,
                args.days,
            )
            seeded_accounts += 1

        await session.commit()

        print("Demo data ready.")
        print(f"Email:       {args.email}")
        print(f"Password:    {args.password}")
        print(f"Organization:{demo_org.name}")
        print(f"Account ID:  {DEFAULT_DEMO_ACCOUNT_ID}")
        print(f"Account Name:{DEFAULT_DEMO_ACCOUNT_NAME}")
        print(f"Accounts:    {seeded_accounts}")
        print(f"Seed:        {args.seed}")
        print(f"Records:     {total_records}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_demo_data(parse_args()))
