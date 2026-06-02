
from src.data_loader import load_all_data

data = load_all_data()

print("\n" + "═" * 50)
print("   FULL DATA LOADER VALIDATION")
print("═" * 50)

# ── 1. Item Master ─────────────────────────────────────────────────────────
print("\n📋 Item Master")
im = data["item_master"]
print(f"   Items: {len(im)}")
print(f"   Combos: {im['is_combo'].sum()}")
print(f"   Columns: {list(im.columns)}")

# ── 2. Monthly Summary ─────────────────────────────────────────────────────
print("\n📅 Monthly Summary")
for month, summary in data["monthly_summary"].items():
    print(f"   {summary['month']}: "
          f"₹{summary['net_sales']:,} revenue, "
          f"{summary['total_orders']} orders")

# ── 3. Menu Mix Report ─────────────────────────────────────────────────────
print("\n🍽️  Menu Mix Report")
mm = data["menu_mix_report"]
print(f"   Items: {len(mm)}")
print(f"   Categories: {sorted(mm['category'].unique())}")
print(f"   Total revenue: ₹{mm['net_amount'].sum():,.0f}")

# ── 4. Item Wise Sales ─────────────────────────────────────────────────────
print("\n📊 Item Wise Sales")
iws = data["item_wise_sales"]
print(f"   Records: {len(iws)}")
print(f"   Date range: {iws['date'].min().date()} to {iws['date'].max().date()}")
print(f"   Total qty sold: {iws['quantity'].sum():,}")
print(f"   Total revenue: ₹{iws['revenue'].sum():,.0f}")

# ── 5. Online Orders ───────────────────────────────────────────────────────
print("\n🌐 Online Orders")
oo = data["online_orders"]
print(f"   Item lines: {len(oo)}")
print(f"   Unique orders: {oo['order_key'].nunique()}")
print(f"   Platforms: {sorted(oo['order_source'].unique())}")

# ── 6. Material Requirements ───────────────────────────────────────────────
print("\n🥩 Material Requirements (April)")
for material, vals in data["material_requirements"].items():
    if vals["kgs"] > 0:
        print(f"   {material}: {vals['kgs']} kg")

# ── 7. Raw Ingredients ─────────────────────────────────────────────────────
print("\n🛒 Raw Ingredients Needed (April)")
for ingredient, kg in data["raw_ingredients"].items():
    print(f"   {ingredient}: {kg} kg")

# ── 8. Metadata ────────────────────────────────────────────────────────────
print("\n📁 Metadata")
for key, val in data["metadata"].items():
    print(f"   {key}: {val}")

# ── 9. Cross-validation ────────────────────────────────────────────────────
print("\n🔍 Cross-validation")
april_summary_revenue = data["monthly_summary"]["april"]["net_sales"]
menu_mix_revenue      = data["menu_mix_report"]["net_amount"].sum()
iws_revenue           = data["item_wise_sales"]["revenue"].sum()

print(f"   April summary net sales:  ₹{april_summary_revenue:,.0f}")
print(f"   Menu mix net revenue:     ₹{menu_mix_revenue:,.0f}")
print(f"   Item wise total revenue:  ₹{iws_revenue:,.0f}")
print(f"   These should be close ↑")

# ── 10. Load errors ────────────────────────────────────────────────────────
errors = data["metadata"]["load_errors"]
if errors:
    print(f"\n⚠️  Load errors: {errors}")
else:
    print(f"\n✅ No load errors — all data sources clean!")