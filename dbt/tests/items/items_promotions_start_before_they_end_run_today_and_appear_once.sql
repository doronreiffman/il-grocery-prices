-- Each promotion on an items row starts on or before it ends, has not ended before the row's day, and appears once on
-- the row (rule P3: one struct a promotion, src/shopper/items.py; _items.yml): one row a row and promotion that breaks
-- any of the three, or whose start or end is missing. A promotion that starts after the day is kept, as the
-- extraction keeps it.
with entries as (
    select chain, store_type, day, barcode, unnest(promotions) as promotion
    from {{ ref('stg_items') }}
)

select chain, store_type, day, barcode, promotion.promotion_id as promotion_id, count(*) as copies
from entries
group by chain, store_type, day, barcode, promotion.promotion_id
having count(*) > 1
    or bool_or(not coalesce(promotion."start" <= promotion."end" and promotion."end" >= day, false))
