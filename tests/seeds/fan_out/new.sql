SELECT o.order_id, o.customer_id, o.amount, a.addr_type, a.city
FROM orders o JOIN addresses a ON o.customer_id = a.customer_id
