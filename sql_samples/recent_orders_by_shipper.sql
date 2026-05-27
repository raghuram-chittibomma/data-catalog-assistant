-- Report: shipped orders with shipper name and destination
SELECT
    o.order_id,
    o.order_date,
    o.shipped_date,
    s.company_name AS shipper_name,
    o.ship_city,
    o.ship_country
FROM public.orders o
INNER JOIN public.shippers s ON s.shipper_id = o.ship_via
WHERE o.shipped_date IS NOT NULL
ORDER BY o.order_date DESC
LIMIT 50;
