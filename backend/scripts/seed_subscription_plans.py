import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.organization import SubscriptionPlan


PLANS = [
    {
        "name": "Free",
        "slug": "free",
        "price_monthly": 0,
        "price_yearly": 0,
        "max_users": 3,
        "max_storage_gb": 5,
        "ai_credits": 50,
        "features": "Dashboard, Leads, Contacts"
    },
    {
        "name": "Starter",
        "slug": "starter",
        "price_monthly": 999,
        "price_yearly": 9990,
        "max_users": 10,
        "max_storage_gb": 20,
        "ai_credits": 500,
        "features": "Everything in Free, Deals, Tasks"
    },
    {
        "name": "Professional",
        "slug": "professional",
        "price_monthly": 2999,
        "price_yearly": 29990,
        "max_users": 50,
        "max_storage_gb": 100,
        "ai_credits": 5000,
        "features": "Everything in Starter, AI, Reports"
    },
    {
        "name": "Business",
        "slug": "business",
        "price_monthly": 6999,
        "price_yearly": 69990,
        "max_users": 200,
        "max_storage_gb": 500,
        "ai_credits": 20000,
        "features": "Everything in Professional"
    },
    {
        "name": "Enterprise",
        "slug": "enterprise",
        "price_monthly": 0,
        "price_yearly": 0,
        "max_users": -1,
        "max_storage_gb": -1,
        "ai_credits": -1,
        "features": "Unlimited Everything"
    }
]


async def seed():
    async with AsyncSessionLocal() as session:

        for plan in PLANS:

            result = await session.execute(
                select(SubscriptionPlan).where(
                    SubscriptionPlan.slug == plan["slug"]
                )
            )

            exists = result.scalar_one_or_none()

            if exists:
                print(f"{plan['name']} already exists")
                continue

            session.add(SubscriptionPlan(**plan))

        await session.commit()

    print("Subscription plans seeded successfully.")


if __name__ == "__main__":
    asyncio.run(seed())