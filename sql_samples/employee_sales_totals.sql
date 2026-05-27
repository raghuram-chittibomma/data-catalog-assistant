-- Report: order count and revenue by sales employee
SELECT
    e.employee_id,
    e.first_name || ' ' || e.last_name AS employee_name,
    COUNT(DISTINCT o.order_id) AS order_count,
    SUM(od.quantity * od.unit_price * (1 - COALESCE(od.discount, 0))) AS revenue
FROM public.employees e
INNER JOIN public.orders o ON o.employee_id = e.employee_id
INNER JOIN public.order_details od ON od.order_id = o.order_id
GROUP BY e.employee_id, e.first_name, e.last_name
ORDER BY revenue DESC NULLS LAST;
