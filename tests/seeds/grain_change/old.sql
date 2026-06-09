SELECT order_id, SUM(qty) AS total_qty FROM line_items GROUP BY order_id
