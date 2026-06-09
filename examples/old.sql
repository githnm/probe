-- Clean orders model: one row per order.
SELECT
    order_id,
    customer_id,
    amount
FROM orders
