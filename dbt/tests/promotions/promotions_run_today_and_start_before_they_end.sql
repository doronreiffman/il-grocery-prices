-- No promotions row has ended before its day, and each starts on or before it ends (rule P3; _promotions.yml): one
-- row a promotions row that breaks either. A promotion that starts after the day is kept (src/shopper/promos.py), so
-- the start is not held to the day.
select chain, store_type, day, promotion_id, group_id, code, starts, ends
from {{ ref('stg_promotions') }}
where not coalesce(ends >= day, false)
    or not coalesce(starts <= ends, false)
