CREATE TABLE orders (order_id INTEGER, customer_id INTEGER, status VARCHAR, order_total DOUBLE, order_date DATE);
CREATE TABLE customers (customer_id INTEGER, customer_name VARCHAR);
CREATE TABLE events (event_id INTEGER, event_at TIMESTAMPTZ);
INSERT INTO orders VALUES
  (1, 10, 'paid', 20, DATE '2024-01-15'),
  (1, 10, 'paid', 20, DATE '2024-01-15'),
  (2, 10, 'paid', 15, DATE '2024-06-01'),
  (3, 11, 'canceled', 5, DATE '2024-03-01'),
  (4, NULL, 'paid', NULL, DATE '2024-12-31'),
  (5, 12, NULL, 8, DATE '2025-01-01'),
  (6, 99, 'paid', 9, DATE '2024-02-01'),
  (7, 12, 'paid', 4, NULL);
INSERT INTO customers VALUES (10, 'a'), (10, 'b'), (11, 'c'), (12, 'd');
INSERT INTO events VALUES
  (1, TIMESTAMPTZ '2024-01-15 12:00:00+00'),
  (2, TIMESTAMPTZ '2024-01-31 23:30:00+00'),
  (3, TIMESTAMPTZ '2024-02-01 00:00:00+00'),
  (4, TIMESTAMPTZ '2024-02-01 04:30:00+00'),
  (5, TIMESTAMPTZ '2024-03-10 04:30:00+00'),
  (6, TIMESTAMPTZ '2024-03-10 12:00:00+00'),
  (7, NULL);
