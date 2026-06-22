# test_tools.py
from src.data_loader import load_all_data

from src.tools import (
    initialise_tools,
    get_monthly_kpis,
    compare_months,
    get_top_items,
    get_category_performance,
    get_low_performing_items,
    get_channel_performance,
    compare_channels_across_months,
    get_daily_trends,
    get_day_of_week_analysis,
    get_peak_hours,
    get_repeat_customers,
    get_material_requirements,
    get_raw_ingredients,
    get_item_daily_sales
)
import json

# ── Load and initialise ────────────────────────────────────────────────────
data = load_all_data()
initialise_tools(data)

def show(title, result):
    print(f"\n{'═'*50}")
    print(f"  {title}")
    print('═'*50)
    print(json.dumps(result, indent=2, default=str))

# ── Test every tool ────────────────────────────────────────────────────────
# show("Monthly KPIs — April",         get_monthly_kpis("april"))
# show("Monthly KPIs — March",         get_monthly_kpis("march"))
# show("Compare Months",               compare_months())
# show("Top 5 Items by Revenue",       get_top_items(5, "revenue"))
# show("Top 5 Items by Quantity",      get_top_items(5, "quantity"))
# show("Category Performance — April", get_category_performance("april"))
# show("Low Performing Items",         get_low_performing_items())
# show("Channel Performance — April",  get_channel_performance("april"))
# show("Channel Comparison MoM",       compare_channels_across_months())
# show("Daily Trends",                 get_daily_trends())
# show("Day of Week Analysis",         get_day_of_week_analysis())
# show("Peak Hours",                   get_peak_hours())
# show("Repeat Customers",             get_repeat_customers())
# show("Material Requirements",        get_material_requirements())
# show("Raw Ingredients",              get_raw_ingredients())
show("Item Daily Sales",             get_item_daily_sales(item_name="Tunday Mutton Galawati", threshold=30))