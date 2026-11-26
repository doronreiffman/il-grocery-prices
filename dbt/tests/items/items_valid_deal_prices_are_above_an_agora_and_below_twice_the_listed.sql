-- A valid deal's price, as the items table shows it (its price, to the agora), is above 0.01 and below twice the row's
-- listed price (rule P4, src/shopper/deals.py; _items.yml): one row a promotion on an items row that is valid and
-- breaks either, or has no price.
with entries as (
    select chain, store_type, day, barcode, listed, unnest(promotions) as promotion
    from {{ ref('stg_items') }}
)

select chain, store_type, day, barcode, listed, promotion.promotion_id as promotion_id, promotion.price as price
from entries
where promotion.valid
    and not coalesce(promotion.price > 0.01 and promotion.price < 2 * listed, false)
