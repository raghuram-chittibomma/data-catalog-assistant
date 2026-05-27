SELECT p.product_name, SUM(od.quantity) AS total_qty
FROM products p
JOIN order_details od ON p.product_id = od.product_id
GROUP BY p.product_name;
