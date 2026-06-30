"""Registry-driven database seeder.

Runs each module's ``seed`` hook in priority order (lower first), so listings
seed before filings, etc. A new module that defines ``seed`` is picked up
automatically.

    python -m core.seed            # create tables + seed empty modules
    python -m core.seed --reset    # drop everything and reseed
"""
from __future__ import annotations

import argparse
import random

from faker import Faker

from core.database import Base, SessionLocal, engine, init_db
from core.registry import discover_modules

# Deterministic synthetic data across runs.
SEED = 2025
Faker.seed(SEED)
random.seed(SEED)


def seed(reset: bool = False) -> None:
    if reset:
        # discover first so all tables are known to metadata before dropping
        discover_modules()
        Base.metadata.drop_all(bind=engine)

    init_db()
    specs = discover_modules()

    with SessionLocal() as db:
        for spec in specs:
            if spec.seed is not None:
                spec.seed(db)
                print(f"  seeded module: {spec.name}")

    print("Seeding complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the stock-exchange database.")
    parser.add_argument("--reset", action="store_true", help="Drop and rebuild tables.")
    args = parser.parse_args()
    seed(reset=args.reset)
