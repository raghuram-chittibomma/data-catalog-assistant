# ETL samples (catalog lineage)

YAML job definitions ingested on refresh. Each job becomes an **`etl:`** asset with source/target lineage (and optional `dependencies` between jobs).

## Jobs

| File | Job name | Sources → targets |
|------|----------|-------------------|
| `load_orders_summary.yaml` | load_orders_summary | customers, orders → orders_summary |
| `load_order_line_facts.yaml` | load_order_line_facts | orders, order_details, products → order_line_fact |
| `load_product_sales_fact.yaml` | load_product_sales_fact | categories, products, order_details → product_sales_fact |
| `refresh_employee_dim.yaml` | refresh_employee_dim | employees → employee_dim |

`load_orders_summary` depends on `refresh_employee_dim`. `load_product_sales_fact` depends on `load_order_line_facts`.

Reporting tables (e.g. `orders_summary`, `product_sales_fact`) are **logical** targets for lineage—they may not exist in the live Northwind database.

## Refresh

```powershell
python batch_jobs\run_refresh_job.py
```
