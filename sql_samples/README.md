# SQL samples (catalog lineage)

Analytical SQL files ingested on refresh. Each file becomes a **`sql:`** asset in Chroma and Postgres metadata, with lineage edges to referenced tables.

## Files

| File | Tables | Demo search phrases |
|------|--------|---------------------|
| `orders_by_customer.sql` | customers, orders | customer order count, top customers |
| `customers_recent_orders.sql` | customers, orders | recent orders, 1998 orders |
| `product_revenue_by_category.sql` | categories, products, order_details | product revenue, category sales |
| `employee_sales_totals.sql` | employees, orders, order_details | employee sales, revenue by employee |
| `recent_orders_by_shipper.sql` | orders, shippers | shipper, shipped orders |

## Refresh after changes

```powershell
conda activate ai-dev
cd C:\Users\raghu\AI-Projects\data-catalog-assistant
python batch_jobs\run_refresh_job.py
```

Target catalog size after refresh: **14 tables + 5 SQL + 4 ETL** (23 vector documents).
