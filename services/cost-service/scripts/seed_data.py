"""
CloudPulse AI - Data Seeding Script
Generates realistic demo data for testing SOTA forecasting.
"""
import asyncio
import random
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models import Base, CloudAccount, CostRecord

settings = get_settings()

# Services to simulate
SERVICES = {
    "Amazon EC2": {"base": 120.0, "volatility": 0.1, "growth": 0.005},
    "Amazon RDS": {"base": 45.0, "volatility": 0.05, "growth": 0.002},
    "Amazon S3": {"base": 15.0, "volatility": 0.02, "growth": 0.01},
    "AWS Lambda": {"base": 8.0, "volatility": 0.3, "growth": 0.01},
    "Amazon CloudFront": {"base": 12.0, "volatility": 0.15, "growth": 0.005},
}

REGIONS = ["us-east-1", "us-west-2", "eu-west-1"]

async def seed_data():
    print("🌱 Starting data seed...")
    
    engine = create_async_engine(str(settings.database_url))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # 1. Create Demo Account
        demo_account = CloudAccount(
            organization_id="org-demo",
            provider="aws",
            account_id="123456789012",
            account_name="Demo Production",
            is_active=True,
            credentials={"access_key_id": "demo", "secret_access_key": "demo"}, # Dummy
        )
        session.add(demo_account)
        await session.flush()
        print(f"Created Demo Account: {demo_account.id}")
        
        # 2. Generate 180 days of history
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=180)
        
        records = []
        current_date = start_date
        
        while current_date <= end_date:
            is_weekend = current_date.weekday() >= 5
            day_of_year = current_date.timetuple().tm_yday
            
            for service_name, profile in SERVICES.items():
                # Base Trend (Linear Growth)
                days_passed = (current_date - start_date).days
                growth_factor = 1 + (profile["growth"] * days_passed)
                
                # Seasonality (Weekly)
                seasonality = 0.8 if is_weekend else 1.0
                
                # Random Noise
                noise = random.uniform(1 - profile["volatility"], 1 + profile["volatility"])
                
                # Anomalies (Random 2% chance of spike)
                spike = 1.0
                if random.random() < 0.02:
                    spike = random.uniform(2.0, 5.0)
                    print(f"  ⚠️ Generated anomaly for {service_name} on {current_date}")
                
                cost = profile["base"] * growth_factor * seasonality * noise * spike
                
                record = CostRecord(
                    cloud_account_id=demo_account.id,
                    date=current_date,
                    granularity="daily",
                    service=service_name,
                    region=random.choice(REGIONS),
                    amount=Decimal(str(round(cost, 4))),
                    currency="USD",
                    usage_quantity=Decimal(str(round(cost * 10, 2))), # Mock usage
                )
                records.append(record)
            
            current_date += timedelta(days=1)
            
            if len(records) >= 1000:
                session.add_all(records)
                await session.commit()
                records = []
                print(f"  Saved batch up to {current_date}...")

        if records:
            session.add_all(records)
            await session.commit()

    print("✅ Seeding complete!")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed_data())
