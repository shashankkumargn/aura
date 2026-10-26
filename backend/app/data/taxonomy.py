"""Canonical catalog subcategories for generated AURA products."""

from __future__ import annotations

PRODUCT_SUBCATEGORIES = {
    "Wireless Neckband Earphones": "Earphones",
    "True Wireless Stereo Earbuds": "Earphones",
    "Budget Wired Earphones with Mic": "Earphones",
    "Over-Ear Noise Cancelling Headphones": "Headphones",
    "Portable Waterproof Bluetooth Speaker": "Bluetooth Speakers",
    "RGB Gaming Soundbar": "Soundbars",
    "Bluetooth Calling Smartwatch": "Smartwatches",
    "Fitness Smart Band with AMOLED Display": "Smart Bands",
    "Rugged Outdoor Smartwatch": "Smartwatches",
    "Luxury Metallic Smartwatch": "Smartwatches",
    "Lightweight Mesh Running Shoes": "Running Shoes",
    "Classic Casual Canvas Sneakers": "Sneakers",
    "Pro Grip Gym & Training Shoes": "Training Shoes",
    "Breathable Slip-On Walking Shoes": "Walking Shoes",
    "RGB Mechanical Gaming Keyboard": "Keyboards",
    "Silent Wireless Office Mouse": "Mice",
    "Wireless Ergonomic Keyboard & Mouse Combo": "Keyboards & Mice",
    "Surround Sound 7.1 Gaming Headset": "Headsets",
    "Water Resistant Laptop Backpack 30L": "Backpacks",
    "Slim Professional Laptop Briefcase": "Laptop Bags",
    "Gym Sports Duffel Bag with Shoe Compartment": "Duffel Bags",
    "Dry-Fit Athletic Training T-Shirt": "T-Shirts",
    "Cotton Blend Workout Track Pants": "Track Pants",
    "Fleece Lined Winter Pullover Hoodie": "Hoodies",
    "Insulated Stainless Steel Water Bottle 1L": "Bottles",
    "Electric Cordless Kettle 1.5L": "Kettles",
    "Digital Touch Screen Air Fryer 4L": "Air Fryers",
}


def product_subcategory(product_name: str, fallback: str | None = None) -> str | None:
    """Return the canonical subcategory for a catalog product name when known."""
    name = (product_name or "").casefold()
    for base_name, subcategory in PRODUCT_SUBCATEGORIES.items():
        if name.endswith(base_name.casefold()):
            return subcategory
    return fallback
