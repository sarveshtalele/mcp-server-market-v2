"""Synthetic seed data for the listings module (real SET tickers, fake numbers)."""
from __future__ import annotations

import random
from datetime import date

from faker import Faker
from sqlalchemy import select

from modules.listings.models import Company

fake = Faker()

# (symbol, name, sector, industry, board, price_band, net_margin_band, div_yield_band)
UNIVERSE: list[tuple] = [
    ("PTT", "PTT Public Company Limited", "Energy & Utilities", "Resources", "SET", (28, 42), (0.04, 0.09), (3.0, 5.5)),
    ("PTTEP", "PTT Exploration and Production PCL", "Energy & Utilities", "Resources", "SET", (120, 175), (0.18, 0.30), (3.5, 6.0)),
    ("GULF", "Gulf Development PCL", "Energy & Utilities", "Resources", "SET", (38, 58), (0.10, 0.18), (1.0, 2.5)),
    ("EGCO", "Electricity Generating PCL", "Energy & Utilities", "Resources", "SET", (110, 160), (0.08, 0.16), (4.0, 6.5)),
    ("BGRIM", "B.Grimm Power PCL", "Energy & Utilities", "Resources", "SET", (20, 34), (0.03, 0.08), (1.5, 3.0)),
    ("RATCH", "Ratch Group PCL", "Energy & Utilities", "Resources", "SET", (28, 42), (0.10, 0.20), (4.5, 6.5)),
    ("KBANK", "Kasikornbank PCL", "Financials", "Banking", "SET", (120, 165), (0.20, 0.32), (3.0, 5.0)),
    ("SCB", "SCB X PCL", "Financials", "Banking", "SET", (95, 130), (0.22, 0.34), (4.0, 7.0)),
    ("BBL", "Bangkok Bank PCL", "Financials", "Banking", "SET", (135, 185), (0.20, 0.30), (3.5, 5.5)),
    ("KTB", "Krung Thai Bank PCL", "Financials", "Banking", "SET", (16, 24), (0.22, 0.30), (3.5, 5.5)),
    ("KTC", "Krungthai Card PCL", "Financials", "Finance & Securities", "SET", (40, 58), (0.28, 0.40), (1.5, 3.0)),
    ("MTC", "Muangthai Capital PCL", "Financials", "Finance & Securities", "SET", (38, 56), (0.25, 0.36), (0.5, 1.5)),
    ("SAWAD", "Srisawad Corporation PCL", "Financials", "Finance & Securities", "SET", (36, 52), (0.28, 0.40), (2.5, 4.0)),
    ("CPALL", "CP All PCL", "Services", "Commerce", "SET", (52, 72), (0.03, 0.06), (1.5, 3.0)),
    ("CPN", "Central Pattana PCL", "Property & Construction", "Property Development", "SET", (55, 78), (0.25, 0.38), (2.0, 3.5)),
    ("CRC", "Central Retail Corporation PCL", "Services", "Commerce", "SET", (30, 46), (0.03, 0.07), (1.5, 3.0)),
    ("HMPRO", "Home Product Center PCL", "Services", "Commerce", "SET", (9, 14), (0.07, 0.11), (3.0, 4.5)),
    ("GLOBAL", "Siam Global House PCL", "Services", "Commerce", "SET", (14, 22), (0.05, 0.09), (1.5, 3.0)),
    ("ADVANC", "Advanced Info Service PCL", "Technology", "Information & Communication Tech", "SET", (190, 255), (0.14, 0.22), (3.5, 5.0)),
    ("TRUE", "True Corporation PCL", "Technology", "Information & Communication Tech", "SET", (8, 14), (-0.05, 0.08), (0.0, 2.0)),
    ("INTUCH", "Intouch Holdings PCL", "Technology", "Information & Communication Tech", "SET", (62, 88), (0.30, 0.45), (4.0, 6.0)),
    ("DELTA", "Delta Electronics (Thailand) PCL", "Technology", "Electronic Components", "SET", (70, 110), (0.10, 0.16), (0.5, 1.5)),
    ("KCE", "KCE Electronics PCL", "Technology", "Electronic Components", "SET", (35, 55), (0.10, 0.18), (2.0, 3.5)),
    ("HANA", "Hana Microelectronics PCL", "Technology", "Electronic Components", "SET", (38, 56), (0.10, 0.17), (3.0, 4.5)),
    ("CPF", "Charoen Pokphand Foods PCL", "Agro & Food Industry", "Food & Beverage", "SET", (20, 30), (0.01, 0.05), (2.5, 4.5)),
    ("TU", "Thai Union Group PCL", "Agro & Food Industry", "Food & Beverage", "SET", (13, 20), (0.02, 0.06), (3.5, 5.5)),
    ("MINT", "Minor International PCL", "Services", "Tourism & Leisure", "SET", (28, 42), (0.04, 0.10), (1.0, 2.5)),
    ("OSP", "Osotspa PCL", "Agro & Food Industry", "Food & Beverage", "SET", (18, 28), (0.10, 0.16), (3.0, 4.5)),
    ("CBG", "Carabao Group PCL", "Agro & Food Industry", "Food & Beverage", "SET", (60, 90), (0.12, 0.20), (1.5, 3.0)),
    ("BDMS", "Bangkok Dusit Medical Services PCL", "Services", "Health Care Services", "SET", (24, 34), (0.14, 0.20), (1.5, 3.0)),
    ("BH", "Bumrungrad Hospital PCL", "Services", "Health Care Services", "SET", (180, 260), (0.22, 0.32), (2.5, 4.0)),
    ("SCC", "The Siam Cement PCL", "Property & Construction", "Construction Materials", "SET", (180, 260), (0.05, 0.11), (4.0, 6.5)),
    ("LH", "Land and Houses PCL", "Property & Construction", "Property Development", "SET", (6, 10), (0.16, 0.26), (5.0, 8.0)),
    ("AP", "AP (Thailand) PCL", "Property & Construction", "Property Development", "SET", (8, 13), (0.13, 0.20), (4.5, 7.0)),
    ("AOT", "Airports of Thailand PCL", "Services", "Transportation & Logistics", "SET", (52, 74), (0.20, 0.34), (1.0, 2.5)),
    ("YGG", "Yggdrazil Group PCL", "Technology", "Digital Content", "mai", (8, 16), (0.08, 0.16), (0.5, 2.0)),
    ("ZIGA", "Ziga Innovation PCL", "Property & Construction", "Steel & Metals", "mai", (2, 5), (0.05, 0.12), (3.0, 5.0)),
]


def seed(db) -> None:
    """Insert companies if none exist. Net-margin band is stashed for filings."""
    if db.scalar(select(Company).limit(1)) is not None:
        return
    for row in UNIVERSE:
        symbol, name, sector, industry, board, price_band, _margin, dy_band = row
        last_price = round(random.uniform(*price_band), 2)
        shares = (
            random.randint(150_000_000, 700_000_000)
            if board == "mai"
            else random.randint(800_000_000, 9_000_000_000)
        )
        db.add(
            Company(
                symbol=symbol,
                company_name=name,
                sector=sector,
                industry=industry,
                market=board,
                listing_date=fake.date_between(date(1995, 1, 1), date(2018, 12, 31)),
                par_value=round(random.choice([0.5, 1.0, 1.0, 5.0]), 2),
                shares_outstanding=shares,
                last_price=last_price,
                market_cap=round(last_price * shares, 2),
                pe_ratio=round(random.uniform(8, 28), 2),
                pb_ratio=round(random.uniform(0.7, 4.5), 2),
                dividend_yield=round(random.uniform(*dy_band), 2),
                is_active=True,
            )
        )
    db.commit()
