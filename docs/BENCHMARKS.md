# Database Indexing Benchmarks

This document outlines the database indexing strategy and performance measurements for the `todos` table based on a dataset of 1,000,000 rows.

## 1. Baseline Queries and Analysis (Before Indexing)

The following three core queries were analyzed using `EXPLAIN ANALYZE`:

**Query 1: User-filtered listing**
```sql
SELECT * FROM todos WHERE user_id = 'ee6f07d8-8971-4c1d-a9c9-2920394a580c' ORDER BY created_at DESC, id DESC;
```
- **Execution Plan**: Parallel Seq Scan
- **Execution Time**: ~79.67 ms
- **Analysis**: PostgreSQL had to scan large portions of the table across multiple workers because there was no index on `user_id`. It then performed an in-memory quicksort to fulfill the `ORDER BY` clause.

**Query 2: Completed filter**
```sql
SELECT * FROM todos WHERE user_id = 'ee6f07d8-8971-4c1d-a9c9-2920394a580c' AND completed = true ORDER BY created_at DESC, id DESC;
```
- **Execution Plan**: Parallel Seq Scan
- **Execution Time**: ~80.45 ms
- **Analysis**: Similar to Query 1, a sequential scan was the only option, discarding 333,312 rows to find the matching 21 rows.

**Query 3: Count by user**
```sql
SELECT COUNT(*) FROM todos WHERE user_id = 'ee6f07d8-8971-4c1d-a9c9-2920394a580c';
```
- **Execution Plan**: Parallel Seq Scan -> Partial Aggregate -> Finalize Aggregate
- **Execution Time**: ~69.30 ms

## 2. Chosen Indexes

Based on the bottlenecks identified above (Parallel Seq Scans and explicit sort steps), the following composite indexes were introduced:

1. `(user_id, created_at DESC)`: Optimizes Query 1 and Query 3. By including `created_at DESC` inside the index, we can often avoid an explicit sort step or speed up retrieval. For Query 3 (Count), it enables an **Index Only Scan**, significantly reducing I/O.
2. `(user_id, completed, created_at DESC)`: Optimizes Query 2. Since `completed` is frequently used alongside `user_id` for filtering active/completed tasks, this index ensures the database can filter and sort in one pass.

## 3. After-Index Benchmarks

After running the Alembic migration, the same queries were analyzed again:

| Query | Before (ms) | After (ms) | Improvement | Plan Change |
|-------|-------------|------------|-------------|-------------|
| User todo list (`user_id` only) | ~79.67 | ~2.65 | ~30x | Parallel Seq Scan -> Bitmap Index Scan + Sort |
| Completed filter (`user_id` + `completed`) | ~80.45 | ~0.89 | ~90x | Parallel Seq Scan -> Bitmap Index Scan + Sort |
| Count by user | ~69.30 | ~0.28 | ~247x | Parallel Seq Scan -> Index Only Scan |

### Why Bitmap Index Scan?
For queries 1 and 2, PostgreSQL chose a `Bitmap Index Scan` instead of a pure `Index Scan`. This is because the query fetches a relatively small number of rows (115 rows) but still needs to access the heap to fetch the full row data (`SELECT *`). Building a bitmap in memory and then fetching the heap blocks sequentially (Bitmap Heap Scan) is often more efficient than random I/O for each row in a pure Index Scan. 

For Query 3, since we only need the count and the `user_id` is in the index, PostgreSQL correctly chose an `Index Only Scan` (`Heap Fetches: 0`), resulting in a massive 247x speedup.

## 4. Tradeoffs

While the read performance improvements are staggering, adding these indexes comes with engineering tradeoffs:

- **Write Latency**: Every `INSERT`, `UPDATE`, and `DELETE` operation on the `todos` table now incurs a penalty because both composite indexes must be synchronously updated in the B-Tree. For an application with millions of reads, this tradeoff is acceptable, but heavy bulk-insert operations will be slower.
- **Storage Overhead**: Composite indexes consume additional disk space and RAM (cache). Two new indexes on a table with 1,000,000 rows will increase the database's memory footprint footprint.
- **Migration Safety**: Running `CREATE INDEX` on a massive production table locks the table for writes. To avoid downtime, it should ideally be run `CONCURRENTLY`, though Alembic's standard `create_index` command does not do this natively without specific configuration (`postgresql_concurrently=True`). In a high-traffic environment, locking the `todos` table during migration could cause an outage.
