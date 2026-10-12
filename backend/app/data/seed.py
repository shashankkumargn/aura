"""Idempotent seed script to populate aura.db with products, customers, orders, and policies."""

from __future__ import annotations

import datetime
import json
import random
from pathlib import Path

from app.db.models import Customer, LoyaltyLedger, Order, OrderItem, PolicyDoc, Product
from app.db.session import SessionLocal, init_db

DATA_DIR = Path(__file__).resolve().parent
SEED_PRODUCTS_FILE = DATA_DIR / "seed_products.json"
SEED_CUSTOMERS_FILE = DATA_DIR / "seed_customers.json"
SEED_ORDERS_FILE = DATA_DIR / "seed_orders.json"
POLICIES_FILE = DATA_DIR / "policies.json"


CATEGORIES_DATA = {
    "Audio": {
        "subcategories": ["Earphones", "Headphones", "Bluetooth Speakers", "Soundbars"],
        "brands": ["boAt", "Sony", "Noise", "JBL", "Boult", "Realme", "OnePlus"],
        "items": [
            ("Wireless Neckband Earphones", "In-ear wireless Bluetooth neckband earphones with magnetic earbuds and fast charging.", 899, 1499),
            ("True Wireless Stereo Earbuds", "TWS earbuds with active noise cancellation, low latency gaming mode, and 30-hour battery.", 1299, 1999),
            ("Budget Wired Earphones with Mic", "Durable tangle-free 3.5mm wired earphones with deep bass and in-line microphone.", 299, 499),
            ("Over-Ear Noise Cancelling Headphones", "Comfortable over-ear wireless headphones with premium spatial audio and 40-hour playback.", 2499, 7999),
            ("Portable Waterproof Bluetooth Speaker", "Compact IPX7 waterproof wireless speaker with punchy bass and 12-hour playtime.", 1199, 3499),
            ("RGB Gaming Soundbar", "Desktop 2.0 channel stereo soundbar with dynamic RGB lighting and Bluetooth 5.3.", 1799, 3999),
        ],
    },
    "Wearables": {
        "subcategories": ["Smartwatches", "Fitness Trackers", "Smart Bands"],
        "brands": ["Noise", "Fire-Boltt", "boAt", "Fastrack", "Titan", "Amazfit"],
        "items": [
            ("Bluetooth Calling Smartwatch", "1.85-inch HD display smartwatch with Bluetooth calling, 100+ sports modes and SpO2 tracking.", 1499, 2999),
            ("Fitness Smart Band with AMOLED Display", "Slim activity tracker band with heart rate monitor, sleep tracking and 14-day battery.", 1899, 2499),
            ("Rugged Outdoor Smartwatch", "Military-grade certified smartwatch with built-in GPS, compass, and titanium bezel.", 3999, 8999),
            ("Luxury Metallic Smartwatch", "Stainless steel strap smartwatch with always-on display and wireless charging.", 2799, 5499),
        ],
    },
    "Footwear": {
        "subcategories": ["Running Shoes", "Sneakers", "Walking Shoes", "Training Shoes"],
        "brands": ["Nike", "Adidas", "Puma", "Sparx", "Campus", "Reebok", "Asian"],
        "items": [
            ("Lightweight Mesh Running Shoes", "Breathable daily running shoes with cushioned EVA sole and shock absorption.", 899, 1999),
            ("Classic Casual Canvas Sneakers", "Everyday street sneakers with lace-up closure and vulcanized rubber sole.", 999, 2499),
            ("Pro Grip Gym & Training Shoes", "Durable sports shoes with high traction outsole and arch support.", 1499, 3999),
            ("Breathable Slip-On Walking Shoes", "Lightweight memory foam slip-on shoes for long walks and daily commuting.", 799, 1699),
        ],
    },
    "Computer Peripherals": {
        "subcategories": ["Keyboards", "Mice", "Headsets", "Monitors"],
        "brands": ["Logitech", "Razer", "Redragon", "Cosmic Byte", "HP", "Dell", "Zebronics"],
        "items": [
            ("RGB Mechanical Gaming Keyboard", "Tactile blue/red switches mechanical keyboard with customizable RGB backlighting.", 1899, 3499),
            ("Silent Wireless Office Mouse", "Ergonomic 2.4GHz wireless optical mouse with quiet click buttons.", 499, 1299),
            ("Wireless Ergonomic Keyboard & Mouse Combo", "Full-sized membrane keyboard with matching wireless precision mouse.", 1299, 2499),
            ("Surround Sound 7.1 Gaming Headset", "Over-ear gaming headphones with noise-cancelling boom mic and 50mm drivers.", 1599, 3999),
        ],
    },
    "Bags & Luggage": {
        "subcategories": ["Backpacks", "Laptop Bags", "Duffel Bags", "Travel Bags"],
        "brands": ["American Tourister", "Wildcraft", "Safari", "Skybags", "F Gear"],
        "items": [
            ("Water Resistant Laptop Backpack 30L", "Spacious 30-liter casual backpack with padded laptop sleeve and USB charging port.", 999, 1899),
            ("Slim Professional Laptop Briefcase", "Executive office messenger bag with luggage trolley strap and water-repellent fabric.", 1299, 2299),
            ("Gym Sports Duffel Bag with Shoe Compartment", "Multipurpose weekend travel duffel bag with separate ventilated shoe pocket.", 699, 1499),
        ],
    },
    "Apparel": {
        "subcategories": ["T-Shirts", "Track Pants", "Hoodies", "Jackets"],
        "brands": ["Puma", "Adidas", "Nike", "Allen Solly", "Roadster", "HRX"],
        "items": [
            ("Dry-Fit Athletic Training T-Shirt", "Moisture-wicking polyester gym t-shirt with anti-odor technology.", 499, 999),
            ("Cotton Blend Workout Track Pants", "Comfortable slim-fit sweatpants with zipper pockets and elastic waistband.", 799, 1499),
            ("Fleece Lined Winter Pullover Hoodie", "Heavyweight warm cotton fleece hoodie with kangaroo pocket.", 1199, 2299),
        ],
    },
    "Home & Kitchen": {
        "subcategories": ["Bottles", "Coffee Makers", "Air Fryers", "Kettles"],
        "brands": ["Milton", "Pigeon", "Prestige", "Philips", "Borosil"],
        "items": [
            ("Insulated Stainless Steel Water Bottle 1L", "Double-wall vacuum insulated flask keeping drinks hot or cold for 24 hours.", 699, 1199),
            ("Electric Cordless Kettle 1.5L", "Stainless steel fast-boiling water kettle with automatic cut-off and dry-boil safety.", 799, 1499),
            ("Digital Touch Screen Air Fryer 4L", "Rapid air circulation low-oil air fryer with 8 preset cooking modes.", 3499, 6999),
        ],
    },
}


def generate_products() -> list[dict]:
    products = []
    pid_counter = 1

    for category, cat_data in CATEGORIES_DATA.items():
        for base_name, desc_tmpl, min_p, max_p in cat_data["items"]:
            for brand in cat_data["brands"][:3]:  # Create 3 brand variations
                p_id = f"P{pid_counter:03d}"
                pid_counter += 1
                price = round(random.randint(min_p, max_p) / 50) * 50 - 1
                if price < min_p:
                    price = min_p

                subcat = random.choice(cat_data["subcategories"])
                full_name = f"{brand} {base_name}"
                description = f"{desc_tmpl} Premium quality design by {brand}."
                tags = [category.lower(), subcat.lower(), brand.lower(), "bestseller" if random.random() > 0.6 else "featured"]
                stock = random.randint(3, 45)
                rating = round(random.uniform(3.8, 4.9), 1)

                products.append({
                    "id": p_id,
                    "name": full_name,
                    "category": category,
                    "subcategory": subcat,
                    "brand": brand,
                    "price": float(price),
                    "currency": "INR",
                    "description": description,
                    "tags": json.dumps(tags),
                    "stock_qty": stock,
                    "image_url": f"https://images.aura.sim/products/{p_id}.jpg",
                    "rating_avg": rating,
                })

    return products


def generate_customers() -> list[dict]:
    first_names = ["Aarav", "Aditi", "Rohan", "Priya", "Rahul", "Sneha", "Vikram", "Ananya", "Karthik", "Pooja", "Arjun", "Neha", "Amit", "Divya", "Suresh", "Meera", "Kabir", "Tanvi", "Varun", "Isha"]
    last_names = ["Sharma", "Verma", "Patel", "Reddy", "Iyer", "Nair", "Gupta", "Kulkarni", "Deshmukh", "Chopra", "Joshi", "Bhat"]
    tiers = ["Bronze", "Silver", "Gold"]
    channels = ["web", "mobile", "whatsapp_sim", "kiosk_sim"]

    customers = []
    # Dedicated demo accounts
    customers.append({
        "id": "u123",
        "name": "Alex Sharma",
        "email": "alex.sharma@example.com",
        "loyalty_points": 450,
        "loyalty_tier": "Gold",
        "channel_preference": "web",
    })
    customers.append({
        "id": "user1",
        "name": "Sam Patel",
        "email": "sam.patel@example.com",
        "loyalty_points": 180,
        "loyalty_tier": "Silver",
        "channel_preference": "whatsapp_sim",
    })

    for i in range(3, 61):
        c_id = f"CUST-{i:03d}"
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        email = f"{name.lower().replace(' ', '.')}{i}@example.com"
        tier = random.choices(tiers, weights=[0.5, 0.35, 0.15])[0]
        points = random.randint(50, 450) if tier == "Bronze" else (random.randint(500, 1400) if tier == "Silver" else random.randint(1500, 3200))
        channel = random.choice(channels)
        customers.append({
            "id": c_id,
            "name": name,
            "email": email,
            "loyalty_points": points,
            "loyalty_tier": tier,
            "channel_preference": channel,
        })

    return customers


def generate_orders(customers: list[dict], products: list[dict]) -> tuple[list[dict], list[dict]]:
    orders = []
    order_items = []
    statuses = ["placed", "packed", "shipped", "delivered"]
    channels = ["web", "mobile", "whatsapp_sim", "kiosk_sim"]

    # Pre-seed dedicated test orders ORD-1001 and ORD-1002
    orders.append({
        "id": "ORD-1001",
        "customer_id": "u123",
        "status": "shipped",
        "channel": "web",
        "placed_at": datetime.datetime.utcnow() - datetime.timedelta(days=2),
        "payment_status": "completed",
        "shipment_status": "in_transit",
    })
    # item for ORD-1001
    order_items.append({
        "order_id": "ORD-1001",
        "product_id": products[0]["id"],
        "qty": 1,
        "unit_price": products[0]["price"],
    })

    orders.append({
        "id": "ORD-1002",
        "customer_id": "u123",
        "status": "delivered",
        "channel": "web",
        "placed_at": datetime.datetime.utcnow() - datetime.timedelta(days=6),
        "payment_status": "completed",
        "shipment_status": "delivered",
    })
    order_items.append({
        "order_id": "ORD-1002",
        "product_id": products[1]["id"],
        "qty": 1,
        "unit_price": products[1]["price"],
    })

    # Generate ~200 historical orders
    for i in range(1003, 1205):
        order_id = f"ORD-{i}"
        cust = random.choice(customers)
        days_ago = random.randint(1, 90)
        placed_time = datetime.datetime.utcnow() - datetime.timedelta(days=days_ago, hours=random.randint(1, 23))
        status = "delivered" if days_ago > 5 else random.choice(statuses)

        orders.append({
            "id": order_id,
            "customer_id": cust["id"],
            "status": status,
            "channel": random.choice(channels),
            "placed_at": placed_time,
            "payment_status": "completed",
            "shipment_status": status,
        })

        # Add 1 to 3 items per order
        num_items = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1])[0]
        chosen_prods = random.sample(products, num_items)
        for prod in chosen_prods:
            order_items.append({
                "order_id": order_id,
                "product_id": prod["id"],
                "qty": random.randint(1, 2),
                "unit_price": prod["price"],
            })

    return orders, order_items


def seed_database() -> None:
    """Idempotently seed the SQLite database with products, customers, orders, and policies."""
    print("Initializing AURA database tables...")
    init_db()

    db = SessionLocal()
    try:
        # 1. Policies
        print("Seeding Policy Documents...")
        if POLICIES_FILE.exists():
            with POLICIES_FILE.open("r", encoding="utf-8") as f:
                policies_data = json.load(f)
            for p in policies_data:
                existing = db.query(PolicyDoc).filter(PolicyDoc.id == p["id"]).first()
                if not existing:
                    db.add(PolicyDoc(**p))
            db.commit()

        # 2. Products
        print("Generating and seeding Products catalog...")
        products = generate_products()
        # Save snapshot to seed_products.json
        with SEED_PRODUCTS_FILE.open("w", encoding="utf-8") as f:
            json.dump(products, f, indent=2)

        for p in products:
            existing_p = db.query(Product).filter(Product.id == p["id"]).first()
            if not existing_p:
                db.add(Product(**p))
        db.commit()

        # 3. Customers
        print("Generating and seeding Customers...")
        customers = generate_customers()
        with SEED_CUSTOMERS_FILE.open("w", encoding="utf-8") as f:
            json.dump(customers, f, indent=2)

        for c in customers:
            existing_c = db.query(Customer).filter(Customer.id == c["id"]).first()
            if not existing_c:
                db.add(Customer(**c))
        db.commit()

        # 4. Orders & OrderItems
        print("Generating and seeding Orders & OrderItems...")
        orders, order_items = generate_orders(customers, products)
        orders_export = []
        for o in orders:
            o_dict = dict(o)
            if isinstance(o_dict.get("placed_at"), (datetime.date, datetime.datetime)):
                o_dict["placed_at"] = o_dict["placed_at"].isoformat()
            o_dict["items"] = [oi for oi in order_items if oi["order_id"] == o["id"]]
            orders_export.append(o_dict)
        with SEED_ORDERS_FILE.open("w", encoding="utf-8") as f:
            json.dump(orders_export, f, indent=2)

        for o in orders:
            existing_o = db.query(Order).filter(Order.id == o["id"]).first()
            if not existing_o:
                db.add(Order(**o))
        db.commit()

        for oi in order_items:
            # check item existence for that order and product
            existing_oi = db.query(OrderItem).filter(
                OrderItem.order_id == oi["order_id"],
                OrderItem.product_id == oi["product_id"],
            ).first()
            if not existing_oi:
                db.add(OrderItem(**oi))
        db.commit()

        # 5. Seed Loyalty Ledger entries
        print("Generating initial loyalty ledger records...")
        for c in customers[:10]:
            existing_l = db.query(LoyaltyLedger).filter(LoyaltyLedger.customer_id == c["id"]).first()
            if not existing_l:
                db.add(LoyaltyLedger(
                    customer_id=c["id"],
                    delta=c["loyalty_points"],
                    reason="Initial sign-up & historical purchases",
                ))
        db.commit()

        # Count summary
        p_count = db.query(Product).count()
        c_count = db.query(Customer).count()
        o_count = db.query(Order).count()
        pol_count = db.query(PolicyDoc).count()

        print("=" * 60)
        print(f"DATABASE SEED COMPLETE! (aura.db)")
        print(f"- Products in catalog: {p_count}")
        print(f"- Registered customers: {c_count}")
        print(f"- Historical orders: {o_count}")
        print(f"- Policy documents: {pol_count}")
        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
