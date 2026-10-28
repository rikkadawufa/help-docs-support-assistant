"""Generate the fictional Cinderpeak Outdoor help documents.

PDFs are built page by page so every fact used by the eval lands on a known
page. Markdown files are written as-is. Everything here is made up.

Usage: python scripts/make_docs.py
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE = ROOT / "knowledge"
UPDATES = ROOT / "knowledge_updates"

BANNER = "Cinderpeak Outdoor | Help Center | <i>Fictional demo content</i>"
CSS = """
body { font-family: sans-serif; font-size: 10.5pt; line-height: 1.45; color: #1d1d1d; }
.banner { font-size: 8pt; color: #777; border-bottom: 1px solid #ccc; padding-bottom: 4px; }
h1 { font-size: 17pt; margin: 14px 0 4px 0; }
h2 { font-size: 12.5pt; margin: 14px 0 4px 0; }
table { border-collapse: collapse; margin: 6px 0; }
th, td { border: 1px solid #999; padding: 4px 8px; text-align: left; }
th { background: #eee; }
.foot { font-size: 8pt; color: #777; }
"""


def table(header: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{h}</th>" for h in header)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


def write_pdf(path: Path, title: str, pages: list[str]) -> None:
    doc = pymupdf.open()
    for i, html in enumerate(pages, start=1):
        page = doc.new_page(width=612, height=792)  # US Letter
        heading = f"<h1>{title}</h1>" if i == 1 else ""
        full = (
            f"<div class='banner'>{BANNER}</div>{heading}{html}"
            f"<p class='foot'>{title} | page {i} of {len(pages)}</p>"
        )
        spare, _ = page.insert_htmlbox(pymupdf.Rect(54, 48, 558, 750), full, css=CSS)
        if spare < 0:
            sys.exit(f"{path.name} page {i}: content does not fit")
    doc.set_metadata({"title": f"{title} (fictional demo)", "author": "Cinderpeak Outdoor (demo)"})
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)


def returns_policy(days: int, version: int, effective: str) -> list[str]:
    return [
        f"""
<p><b>Version {version}, effective {effective}.</b></p>
<h2>Return window</h2>
<p>You can return most items within {days} days of delivery for a full refund.
Items must be unused and in their original packaging, with all parts and manuals included.</p>
<h2>Items we can't take back</h2>
<p>Fuel canisters and used water filters cannot be returned for safety and hygiene reasons.
Gift cards cannot be returned.</p>
<h2>Defective items</h2>
<p>If an item arrives damaged or stops working because of a manufacturing defect, see our Warranty
Policy instead. Defective items are handled as warranty claims, not returns.</p>
""",
        """
<h2>How to start a return</h2>
<p>Sign in to your account, open <b>Orders</b>, choose the order and select <b>Start a return</b>.
We email you a prepaid return label within one business day.</p>
<h2>Return shipping</h2>
<p>Return shipping is free for defective items. For all other returns, a $7.95 return shipping fee
is deducted from your refund.</p>
<h2>Refunds</h2>
<p>Refunds are issued to the original payment method within 5&ndash;7 business days after we receive
and inspect the item. You will get an email when the refund is issued.</p>
<h2>Exchanges</h2>
<p>We don't offer direct exchanges. Return the item for a refund and place a new order for the item you want.</p>
""",
    ]


PDFS: dict[str, tuple[str, list[str]]] = {
    "returns-policy.pdf": ("Returns Policy", returns_policy(30, 1, "January 1, 2026")),
    "warranty.pdf": (
        "Limited Warranty",
        [
            """
<p>Cinderpeak Outdoor products are covered by a limited warranty against defects in materials and
workmanship. The warranty applies to the original purchaser and starts on the delivery date.
Proof of purchase (an order number or receipt) is required for every claim.</p>
<p>This page gives an overview. Warranty periods for each product line are on page 2.
What is not covered and how to file a claim are on page 3.</p>
""",
            "<h2>Warranty periods by product line</h2>"
            + table(
                ["Product line", "Example products", "Warranty period"],
                [
                    ["Camp stoves", "Ember 2", "3 years"],
                    ["Lanterns", "Halo LED Lantern", "2 years"],
                    ["Coolers", "Glacier 45", "5 years"],
                    ["Sleeping bags", "Drift 20", "1 year"],
                    ["Power banks", "Volt 10K", "1 year"],
                ],
            )
            + """
<p><b>Built-in batteries:</b> rechargeable batteries inside lanterns and power banks are covered
for 1 year, regardless of the product line's warranty period.</p>
""",
            """
<h2>What is not covered</h2>
<p>Normal wear and tear, cosmetic scratches, damage from misuse or accidents, damage from using
fuel that is not approved in the product manual, and products used for commercial purposes.</p>
<h2>How to file a warranty claim</h2>
<p>Email warranty@cinderpeak.example with your order number, a short description of the problem
and photos of the issue. We reply within 2 business days.</p>
<h2>What we do</h2>
<p>If the claim is approved, we repair the item, replace it, or refund the purchase price,
at our discretion. We pay shipping both ways for approved claims.</p>
""",
        ],
    ),
    "shipping-rates.pdf": (
        "Shipping Rates and Delivery Times",
        [
            "<h2>United States (contiguous 48 states)</h2>"
            + table(
                ["Order subtotal", "Standard shipping"],
                [["Under $35.00", "$6.95"], ["$35.00 to $74.99", "$9.95"], ["$75.00 and over", "Free"]],
            )
            + "<p>Expedited shipping (2 business days) is a flat $19.95 on any order.</p>"
            + "<h2>Canada</h2>"
            + table(
                ["Order subtotal (USD)", "Standard shipping"],
                [["Under $150.00", "$14.95"], ["$150.00 and over", "Free"]],
            )
            + "<p>Expedited shipping is not available to Canada.</p>",
            """
<h2>Processing time</h2>
<p>Orders placed before 2 p.m. Eastern Time on a business day ship the same day.
Orders placed later ship the next business day.</p>
<h2>Delivery times</h2>
<p>Standard delivery takes 3&ndash;6 business days in the contiguous United States and
5&ndash;10 business days to Canada, after the order ships.</p>
<h2>Duties and taxes</h2>
<p>Canadian orders may be charged duties and taxes, which the customer pays on delivery.</p>
<h2>PO boxes</h2>
<p>We ship to PO boxes with standard shipping only. Expedited orders need a street address.</p>
""",
        ],
    ),
    "manual-ember-2-stove.pdf": (
        "Ember 2 Camp Stove - Owner's Manual",
        [
            "<h2>Specifications</h2>"
            + table(
                ["Item", "Value"],
                [
                    ["Burners", "2"],
                    ["Output", "10,000 BTU per burner"],
                    ["Fuel", "16.4 oz propane canister"],
                    ["Weight", "11.2 lb"],
                    ["Cooking surface", "Fits two 10-inch pans"],
                ],
            )
            + "<p>Approved fuel: 16.4 oz propane canisters only.</p>",
            """
<h2>Safety</h2>
<p><b>Never use the Ember 2 indoors, inside a tent, or in any enclosed space.</b> The stove produces
carbon monoxide, which can kill. Keep the stove at least 3 feet from tents, trees and other
flammable objects.</p>
<h2>Lighting the stove</h2>
<p>1. Connect the regulator to the stove and screw in the propane canister by hand.<br>
2. Open the lid and set the stove on a flat, stable surface.<br>
3. Turn the burner knob to HIGH and press the igniter button until the burner lights.<br>
4. Adjust the flame with the knob.</p>
""",
            """
<h2>Troubleshooting</h2>
<p><b>Weak or uneven flame:</b> check that the regulator is fully tightened. In cold weather
(below 40&deg;F) propane pressure drops; keep the canister warm before use.</p>
<p><b>Igniter does not spark:</b> wipe the igniter tip with a dry cloth. You can light the burner
with a long match.</p>
<h2>Cleaning</h2>
<p>Let the stove cool completely. Clean burner ports with a soft brush. Do not use a pin or
wire, which can enlarge the ports.</p>
""",
        ],
    ),
    "manual-halo-lantern.pdf": (
        "Halo LED Lantern - Owner's Manual",
        [
            "<h2>Specifications</h2>"
            + table(
                ["Item", "Value"],
                [
                    ["Brightness", "400 lumens (high), 60 lumens (low)"],
                    ["Battery", "5,200 mAh built-in rechargeable"],
                    ["Runtime", "6 hours on high, 40 hours on low"],
                    ["Charging", "USB-C, about 4 hours to full"],
                    ["Water resistance", "IPX4 (splash resistant)"],
                ],
            ),
            """
<h2>Using the lantern</h2>
<p>Press the power button once for high, twice for low, and three times for red night mode.
Hold the button for 2 seconds to turn the lantern off.</p>
<h2>Charging</h2>
<p>Use the included USB-C cable. The indicator light is red while charging and turns green when full.</p>
<h2>Water</h2>
<p>The Halo is splash resistant but not waterproof. Do not submerge it.</p>
""",
        ],
    ),
    "manual-glacier-45-cooler.pdf": (
        "Glacier 45 Cooler - Owner's Manual",
        [
            "<h2>Specifications</h2>"
            + table(
                ["Item", "Value"],
                [
                    ["Capacity", "45 quarts"],
                    ["Ice retention", "Up to 5 days"],
                    ["Empty weight", "23 lb"],
                    ["Drain", "Threaded drain plug with tether"],
                ],
            )
            + "<p>Ice retention was measured at 70&deg;F with a pre-chilled cooler, a 2:1 ice-to-contents ratio and the lid kept closed.</p>",
            """
<h2>Getting the most ice life</h2>
<p>Pre-chill the cooler with a bag of sacrificial ice the night before. Keep it out of direct sun
and open the lid as little as possible.</p>
<h2>Cleaning</h2>
<p>Wash with warm water and mild dish soap. Do not use bleach or abrasive cleaners. Leave the lid
open to dry completely before storage.</p>
""",
        ],
    ),
    "manual-drift-20-sleeping-bag.pdf": (
        "Drift 20 Sleeping Bag - Owner's Manual",
        [
            "<h2>Specifications</h2>"
            + table(
                ["Item", "Value"],
                [
                    ["Comfort rating", "32&deg;F"],
                    ["Lower limit", "20&deg;F"],
                    ["Fill", "Synthetic insulation"],
                    ["Weight", "3.1 lb"],
                ],
            ),
            """
<h2>Washing</h2>
<p>Machine wash on a gentle cycle in cold water, in a front-loading machine only. Top-loading machines
with an agitator can tear the baffles. Use a mild, non-detergent soap.</p>
<p>Tumble dry on low heat with two clean tennis balls to break up clumps.</p>
<h2>Storage</h2>
<p>Store the bag loose in the large mesh sack, not in the compression sack. Long-term compression
reduces loft and warmth.</p>
""",
        ],
    ),
    "manual-volt-10k-power-bank.pdf": (
        "Volt 10K Power Bank - Owner's Manual",
        [
            "<h2>Specifications</h2>"
            + table(
                ["Item", "Value"],
                [
                    ["Capacity", "10,000 mAh (37 Wh)"],
                    ["Ports", "1 USB-C (20W in/out), 1 USB-A (12W out)"],
                    ["Recharge time", "About 3 hours with a 20W USB-C charger"],
                ],
            ),
            """
<h2>Air travel</h2>
<p>The Volt 10K is rated at 37 Wh. Most airlines allow power banks under 100 Wh in carry-on
luggage only. Check your airline's rules before you fly.</p>
<h2>Storage</h2>
<p>For long-term storage, charge to about 50% and recharge every 3 months.</p>
""",
        ],
    ),
}

MARKDOWN: dict[str, str] = {
    "faq.md": """# Frequently Asked Questions

_Cinderpeak Outdoor Help Center. Fictional demo content._

## Payment methods
We accept Visa, Mastercard, American Express, Discover, PayPal and Apple Pay. We do not offer cash on delivery.

## Order tracking
When your order ships, we email you a tracking link. Tracking can take up to 24 hours to show the first update.

## Customer support hours
Our support team answers email at support@cinderpeak.example, Monday to Friday, 9 a.m. to 5 p.m. Eastern Time.
We reply within 1 business day.

## Creating an account
You can check out as a guest. An account lets you see past orders and start returns online.
""",
    "order-changes.md": """# Changing or Canceling an Order

_Cinderpeak Outdoor Help Center. Fictional demo content._

## Within 1 hour of ordering
You can change the shipping address or cancel the order yourself within 1 hour of placing it.
Sign in, open **Orders** and choose **Edit** or **Cancel order**.

## After 1 hour
After 1 hour, your order may already be packed and we can't change or cancel it.
Once it arrives, you can return it under our Returns Policy.

## Adding items
We can't add items to an order that has been placed. Please place a second order.
""",
    "gift-cards-and-promos.md": """# Gift Cards and Promo Codes

_Cinderpeak Outdoor Help Center. Fictional demo content._

## Gift cards
Gift cards never expire and have no fees. They can't be exchanged for cash, except where required by law.
Lost gift cards can be replaced if you have the original order number.

## Promo codes
You can use one promo code per order. Promo codes cannot be combined with each other.
Promo codes can't be used to buy gift cards.
A promo code must be entered at checkout. We can't apply a code to an order after it has been placed.
""",
    "care-and-storage.md": """# Care and Storage

_Cinderpeak Outdoor Help Center. Fictional demo content._

## After every trip
Dry all gear completely before you store it. Moisture causes mildew on fabric and corrosion on metal parts.

## Fuel canisters
Store propane canisters outdoors or in a well-ventilated area, away from heat. Never store them inside a car in hot weather.

## Batteries
Charge lanterns and power banks to about 50% before storing them for more than a month.
""",
    "international-shipping.md": """# International Shipping

_Cinderpeak Outdoor Help Center. Fictional demo content._

## Where we ship
We ship only to the United States and Canada. We do not ship to any other country.

## Alaska and Hawaii
Orders to Alaska and Hawaii ship by standard shipping only, for a flat $24.95. Free shipping does not apply.

## Freight forwarders
We can't ship to freight forwarding or reshipping services.
""",
    "spare-parts.md": """# Spare Parts

_Cinderpeak Outdoor Help Center. Fictional demo content._

## Parts you can order
- Ember 2: regulator, burner grate, igniter assembly
- Glacier 45: drain plug, latch set, lid gasket
- Halo LED Lantern: hanging hook, USB-C charging cable

## How to order
Email support@cinderpeak.example with the product name and the part you need. We reply with a quote and a payment link.
""",
    "trailpoints-rewards.md": """# Trailpoints Rewards

_Cinderpeak Outdoor Help Center. Fictional demo content._

## Earning points
Members earn 1 Trailpoint for every $1 spent on products, before tax and shipping.

## Redeeming points
Every 100 Trailpoints can be redeemed for $5 off a future order. Points expire 12 months after they are earned.

## Joining
Joining is free. Create an account and turn on Trailpoints in your account settings.
""",
    "privacy-and-account.md": """# Privacy and Your Account

_Cinderpeak Outdoor Help Center. Fictional demo content._

## Deleting your account
Email support@cinderpeak.example from the address on your account and ask us to delete it. We delete account data within 30 days.

## Email preferences
Use the unsubscribe link at the bottom of any marketing email. Order and shipping emails are always sent.
""",
}

# Answers to the trap questions must not exist anywhere in the documents.
TRAP_PATTERNS = [
    r"price[- ]match", r"\brent(al|ing|s)?\b", r"military", r"student", r"retail store",
    r"showroom", r"solar", r"in stock|restock|back in stock", r"mobile app", r"gift wrap",
    r"group trip|guided trip",
]


def check_traps(texts: dict[str, str]) -> list[str]:
    hits = []
    for name, text in texts.items():
        for pat in TRAP_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                hits.append(f"{name}: {pat}")
    return hits


def main() -> None:
    KNOWLEDGE.mkdir(exist_ok=True)
    UPDATES.mkdir(exist_ok=True)
    texts: dict[str, str] = {}
    for name, (title, pages) in PDFS.items():
        path = KNOWLEDGE / name
        write_pdf(path, title, pages)
        with pymupdf.open(path) as doc:
            texts[name] = "\n".join(p.get_text() for p in doc)
    for name, body in MARKDOWN.items():
        (KNOWLEDGE / name).write_text(body, encoding="utf-8")
        texts[name] = body

    # Keep both versions so swap_returns_policy.py can copy them byte for byte
    # (PyMuPDF output is not byte-identical between runs).
    shutil.copyfile(KNOWLEDGE / "returns-policy.pdf", UPDATES / "returns-policy-v1.pdf")
    v2 = UPDATES / "returns-policy-v2.pdf"
    write_pdf(v2, "Returns Policy", returns_policy(14, 2, "November 1, 2026"))
    with pymupdf.open(v2) as doc:
        texts["updates/returns-policy.pdf"] = "\n".join(p.get_text() for p in doc)

    hits = check_traps(texts)
    print(f"wrote {len(PDFS)} PDFs + {len(MARKDOWN)} Markdown files to knowledge/, returns policy v1 + v2 to knowledge_updates/")
    print("trap keyword check:", "PASS (0 hits)" if not hits else "FAIL")
    for h in hits:
        print("  ", h)
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
