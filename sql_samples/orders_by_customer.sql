-- Northwind-style: orders per customer
SELECT
    c.company_name,
    COUNT(o.order_id) AS order_count
FROM public.customers c
LEFT JOIN public.orders o ON o.customer_id = c.customer_id
GROUP BY c.company_name
ORDER BY order_count DESC;
