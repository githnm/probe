# Probe UI: input reference

Every box, in order, for both ways to run the UI. Fill the sidebar once, then go tab by tab.

Two rules that keep tripping things up:
- The `.json` file goes in the manifest box. The `.duckdb` file goes in the DuckDB box. Never swap them.
- Setup A fills Setup SQL and leaves the manifest empty. Setup B fills the manifest and leaves Setup SQL empty. Do not mix them.

---

## Setup A: the self-contained demo (no dbt)

Use this for the fan-out story. Everything lives in memory.

### Sidebar
- DuckDB path: `:memory:`
- dbt manifest.json path: leave empty
- Setup SQL:
```
CREATE TABLE orders(order_id INT, amount INT); INSERT INTO orders VALUES (1,100),(2,200),(3,300); CREATE TABLE addr(order_id INT, city TEXT); INSERT INTO addr VALUES (1,'NYC'),(1,'LA'),(2,'SF'),(2,'DAL'),(3,'CHI'),(3,'MIA');
```
- Key column: `order_id`
- Metric columns: `amount`

### Tables tab
Nothing to type. You should see `orders` and `addr` with previews.

### Diff tab
- Old SQL:
```
SELECT order_id, amount FROM orders
```
- New SQL:
```
SELECT o.order_id, o.amount, a.city FROM orders o JOIN addr a ON o.order_id = a.order_id
```
- Explain: tick only if you set your API key in the terminal before launching the app.

### Lineage and Verify tabs
Skip these in Setup A. There is no manifest and no staging models to trace.

---

## Setup B: the real dbt project (jaffle)

Use this for the lineage graph, table browsing, and verify.

### Sidebar
- DuckDB path:
```
/Users/hoshangmehta/jaffle_shop_duckdb/jaffle_shop.duckdb
```
- dbt manifest.json path:
```
/Users/hoshangmehta/jaffle_shop_duckdb/target/manifest.json
```
- Setup SQL: leave empty (the data is already in the file)
- Key column: `order_id`
- Metric columns: leave empty

### Tables tab
Nothing to type. You should see all the jaffle models and seeds with previews.

### Lineage tab
Pick `stg_orders` from the model dropdown. Its downstream models light up, with the impacted columns listed.

### Diff tab
- Old SQL:
```
SELECT order_id, customer_id, order_date, status FROM stg_orders
```
- New SQL:
```
SELECT o.order_id, o.customer_id, o.order_date, o.status, p.amount FROM stg_orders o JOIN stg_payments p ON o.order_id = p.order_id
```
- Explain: optional, key required.

### Verify tab
- Upstream model: `stg_orders`
- Downstream model: `orders`
- Upstream query:
```
SELECT * FROM stg_orders
```
- Downstream query:
```
SELECT * FROM orders
```
- Column mappings: leave empty (it auto-matches same-named columns)

Expected: `order_id`, `customer_id`, `order_date`, `status` verify as real passthroughs. The payment-derived columns in `orders` show unverified, because they are not in `stg_orders` to compare against. That mix is the correct result.

---

## Notes

- The manifest path drives the dropdowns and the lineage graph. The DuckDB path drives the actual data. For jaffle, both must point at the jaffle project at the same time.
- The Explain checkbox needs `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`) set in the terminal that launched `probe-ui`. Set it before running the app, then run the diff.
