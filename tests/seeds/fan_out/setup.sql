CREATE TABLE orders (order_id INT, customer_id INT, amount DOUBLE);
INSERT INTO orders VALUES (1, 100, 50.0), (2, 100, 75.0), (3, 200, 120.0), (4, 300, 30.0), (5, 200, 200.0);
CREATE TABLE addresses (customer_id INT, addr_type TEXT, city TEXT);
INSERT INTO addresses VALUES (100, 'billing', 'NYC'), (100, 'shipping', 'Boston'), (200, 'billing', 'Chicago'), (200, 'shipping', 'Chicago'), (200, 'warehouse', 'Denver'), (300, 'billing', 'Seattle')
