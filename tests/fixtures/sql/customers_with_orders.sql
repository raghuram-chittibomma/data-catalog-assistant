-- Sample report: customers with recent orders
SELECT
    c.customer_id,
    c.company_name,
    o.order_id,
    o.order_date
FROM public.customers AS c
INNER JOIN public.orders AS o ON c.customer_id = o.customer_id
WHERE o.order_date >= '1998-01-01'
ORDER BY o.order_date DESC;
