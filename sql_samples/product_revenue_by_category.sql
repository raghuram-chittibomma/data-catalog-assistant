-- Report: product revenue and units sold, rolled up by category
SELECT
    c.category_name,
    p.product_name,
    SUM(od.quantity * od.unit_price * (1 - COALESCE(od.discount, 0))) AS line_revenue,
    SUM(od.quantity) AS units_sold
FROM public.categories c
INNER JOIN public.products p ON p.category_id = c.category_id
INNER JOIN public.order_details od ON od.product_id = p.product_id
GROUP BY c.category_name, p.product_name
ORDER BY line_revenue DESC;
