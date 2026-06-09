-- Joins customer_addresses (one-to-many): fans out rows, doubles revenue.
SELECT
    o.order_id,
    o.customer_id,
    o.amount,
    a.address_type,
    a.city
FROM orders o
JOIN customer_addresses a ON o.customer_id = a.customer_id
