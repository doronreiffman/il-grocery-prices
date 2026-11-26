-- A valid deal's price as shown, to the agora (the struct's price), is above 0.01 and below twice the row's listed
-- price (docs/dbt-layer.md, section 3; _items.yml): one row a promotion on an items row that is valid and breaks either,
-- or has no price. src/shopper/deals.py judges rule P4 on the exact price, so the two can differ only for a deal whose
-- exact price is not a whole number of agorot and lies within half an agora above 0.01 or below twice the listed price.
with entries as (
    select chain, store_type, day, barcode, listed, unnest(promotions) as promotion
    from {{ ref('stg_items') }}
)

select chain, store_type, day, barcode, listed, promotion.promotion_id as promotion_id, promotion.price as price
from entries
where promotion.valid
    and not coalesce(promotion.price > 0.01 and promotion.price < 2 * listed, false)
