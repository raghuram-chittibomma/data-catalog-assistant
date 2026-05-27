-- Report: customers with orders in a date range (recent activity)
SELECT
    c.customer_id,
    c.company_name,
    c.contact_name,
    o.order_id,
    o.order_date,
    o.freight
FROM public.customers c
INNER JOIN public.orders o ON o.customer_id = c.customer_id
WHERE o.order_date >= DATE '1998-01-01'
ORDER BY o.order_date DESC, c.company_name;
