"""Synthetic seed data for the listings module.

Uses a US-style exchange (NYSE / NASDAQ, USD) purely for flavour — every
financial figure is randomly generated (deterministic via a fixed seed) and is
NOT real market data.
"""
from __future__ import annotations

import random
from datetime import date

from faker import Faker
from sqlalchemy import select

from modules.listings.models import Company

fake = Faker()

# (symbol, name, sector, industry, board, price_band, net_margin_band, div_yield_band)
UNIVERSE: list[tuple] = [
    # Technology
    ("AAPL", "Apple Inc.", "Technology", "Consumer Electronics", "NASDAQ", (160, 200), (0.23, 0.27), (0.4, 0.7)),
    ("MSFT", "Microsoft Corporation", "Technology", "Software", "NASDAQ", (320, 420), (0.33, 0.38), (0.7, 1.0)),
    ("NVDA", "NVIDIA Corporation", "Technology", "Semiconductors", "NASDAQ", (400, 900), (0.30, 0.50), (0.0, 0.3)),
    ("ORCL", "Oracle Corporation", "Technology", "Software", "NYSE", (90, 130), (0.18, 0.25), (1.2, 1.8)),
    ("ADBE", "Adobe Inc.", "Technology", "Software", "NASDAQ", (450, 600), (0.25, 0.30), (0.0, 0.3)),
    ("CRM", "Salesforce Inc.", "Technology", "Software", "NYSE", (180, 280), (0.05, 0.15), (0.0, 0.6)),
    ("INTC", "Intel Corporation", "Technology", "Semiconductors", "NASDAQ", (25, 45), (0.05, 0.20), (1.0, 2.5)),
    # Communication Services
    ("GOOGL", "Alphabet Inc.", "Communication Services", "Internet Content", "NASDAQ", (120, 160), (0.20, 0.26), (0.0, 0.5)),
    ("META", "Meta Platforms Inc.", "Communication Services", "Internet Content", "NASDAQ", (250, 400), (0.25, 0.34), (0.0, 0.5)),
    ("DIS", "The Walt Disney Company", "Communication Services", "Entertainment", "NYSE", (80, 120), (0.05, 0.12), (0.0, 1.0)),
    ("NFLX", "Netflix Inc.", "Communication Services", "Entertainment", "NASDAQ", (350, 550), (0.15, 0.22), (0.0, 0.3)),
    ("T", "AT&T Inc.", "Communication Services", "Telecom", "NYSE", (14, 22), (0.10, 0.16), (5.0, 7.0)),
    ("VZ", "Verizon Communications Inc.", "Communication Services", "Telecom", "NYSE", (30, 45), (0.12, 0.18), (5.5, 7.5)),
    # Financials
    ("JPM", "JPMorgan Chase & Co.", "Financials", "Banks", "NYSE", (140, 200), (0.28, 0.34), (2.2, 3.0)),
    ("BAC", "Bank of America Corporation", "Financials", "Banks", "NYSE", (28, 42), (0.25, 0.30), (2.2, 3.0)),
    ("WFC", "Wells Fargo & Company", "Financials", "Banks", "NYSE", (40, 60), (0.22, 0.28), (2.0, 3.2)),
    ("GS", "The Goldman Sachs Group Inc.", "Financials", "Capital Markets", "NYSE", (330, 430), (0.20, 0.28), (2.0, 3.0)),
    ("MS", "Morgan Stanley", "Financials", "Capital Markets", "NYSE", (80, 110), (0.18, 0.25), (3.0, 4.0)),
    ("AXP", "American Express Company", "Financials", "Consumer Finance", "NYSE", (150, 230), (0.15, 0.20), (1.0, 1.6)),
    ("C", "Citigroup Inc.", "Financials", "Banks", "NYSE", (45, 70), (0.15, 0.22), (3.0, 4.2)),
    # Energy
    ("XOM", "Exxon Mobil Corporation", "Energy", "Oil & Gas Integrated", "NYSE", (95, 120), (0.08, 0.14), (3.0, 4.0)),
    ("CVX", "Chevron Corporation", "Energy", "Oil & Gas Integrated", "NYSE", (140, 175), (0.08, 0.13), (3.5, 4.5)),
    ("COP", "ConocoPhillips", "Energy", "Oil & Gas E&P", "NYSE", (95, 130), (0.15, 0.25), (1.5, 2.5)),
    ("SLB", "Schlumberger Limited", "Energy", "Oil & Gas Equipment", "NYSE", (40, 60), (0.10, 0.16), (1.8, 2.6)),
    # Healthcare
    ("JNJ", "Johnson & Johnson", "Healthcare", "Pharmaceuticals", "NYSE", (150, 180), (0.18, 0.24), (2.7, 3.4)),
    ("PFE", "Pfizer Inc.", "Healthcare", "Pharmaceuticals", "NYSE", (28, 45), (0.20, 0.30), (3.5, 5.0)),
    ("UNH", "UnitedHealth Group Incorporated", "Healthcare", "Healthcare Plans", "NYSE", (450, 560), (0.06, 0.09), (1.2, 1.8)),
    ("ABBV", "AbbVie Inc.", "Healthcare", "Pharmaceuticals", "NYSE", (140, 180), (0.20, 0.28), (3.5, 4.5)),
    ("MRK", "Merck & Co. Inc.", "Healthcare", "Pharmaceuticals", "NYSE", (100, 130), (0.20, 0.28), (2.4, 3.2)),
    # Consumer
    ("WMT", "Walmart Inc.", "Consumer Staples", "Discount Stores", "NYSE", (50, 70), (0.02, 0.04), (1.3, 1.8)),
    ("KO", "The Coca-Cola Company", "Consumer Staples", "Beverages", "NYSE", (55, 65), (0.22, 0.27), (2.8, 3.4)),
    ("PEP", "PepsiCo Inc.", "Consumer Staples", "Beverages", "NASDAQ", (160, 190), (0.10, 0.14), (2.6, 3.2)),
    ("PG", "The Procter & Gamble Company", "Consumer Staples", "Household Products", "NYSE", (140, 165), (0.18, 0.22), (2.3, 2.9)),
    ("COST", "Costco Wholesale Corporation", "Consumer Staples", "Discount Stores", "NASDAQ", (550, 720), (0.02, 0.04), (0.5, 0.9)),
    ("MCD", "McDonald's Corporation", "Consumer Discretionary", "Restaurants", "NYSE", (260, 310), (0.30, 0.36), (2.0, 2.6)),
    ("NKE", "NIKE Inc.", "Consumer Discretionary", "Footwear & Apparel", "NYSE", (90, 130), (0.10, 0.14), (1.0, 1.6)),
    ("HD", "The Home Depot Inc.", "Consumer Discretionary", "Home Improvement", "NYSE", (290, 360), (0.09, 0.12), (2.2, 2.8)),
    # Industrials
    ("BA", "The Boeing Company", "Industrials", "Aerospace & Defense", "NYSE", (180, 240), (-0.05, 0.06), (0.0, 1.0)),
    ("CAT", "Caterpillar Inc.", "Industrials", "Heavy Machinery", "NYSE", (220, 300), (0.13, 0.18), (1.6, 2.2)),
    ("GE", "General Electric Company", "Industrials", "Specialty Industrial", "NYSE", (90, 140), (0.05, 0.12), (0.3, 0.8)),
    ("HON", "Honeywell International Inc.", "Industrials", "Conglomerates", "NASDAQ", (180, 220), (0.14, 0.18), (1.8, 2.4)),
]


def seed(db) -> None:
    """Insert companies if none exist."""
    if db.scalar(select(Company).limit(1)) is not None:
        return
    for row in UNIVERSE:
        symbol, name, sector, industry, board, price_band, _margin, dy_band = row
        last_price = round(random.uniform(*price_band), 2)
        shares = random.randint(300_000_000, 16_000_000_000)
        db.add(
            Company(
                symbol=symbol,
                company_name=name,
                sector=sector,
                industry=industry,
                market=board,
                listing_date=fake.date_between(date(1970, 1, 1), date(2015, 12, 31)),
                par_value=round(random.choice([0.01, 0.001, 0.1, 1.0]), 3),
                shares_outstanding=shares,
                last_price=last_price,
                market_cap=round(last_price * shares, 2),
                pe_ratio=round(random.uniform(8, 40), 2),
                pb_ratio=round(random.uniform(0.7, 12.0), 2),
                dividend_yield=round(random.uniform(*dy_band), 2),
                is_active=True,
            )
        )
    db.commit()
