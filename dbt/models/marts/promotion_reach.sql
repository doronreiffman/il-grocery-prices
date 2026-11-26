-- Is a promotion on at most branches, or at a few? (promotion_reach.yml). A promotions row counts when its code is a
-- GS1 barcode, it has a kind, it runs on the day (rule P3: starts on or before it, ends on or after it) and the items
-- table lists the product at that chain, store type and day. Each promotion is then one entry a store type and day:
-- at most branches when any of its rows counting is wide (P3), with a restriction or a minimum spend (P5) when any
-- of them has one.
with listed_promotions as (
    select
        promotion.store_type,
        promotion.day,
        promotion.promotion_id,
        bool_or(promotion.wide) as wide,
        bool_or(len(promotion.restrictions) > 0) as has_restriction,
        bool_or(promotion.min_spend is not null) as has_min_spend
    from {{ ref('stg_promotions') }} as promotion
    join {{ ref('stg_items') }} as item
        on item.chain = promotion.chain
        and item.store_type = promotion.store_type
        and item.day = promotion.day
        and item.barcode = promotion.barcode
    where promotion.gs1
        and promotion.kind is not null
        and promotion.starts <= promotion.day
        and promotion.day <= promotion.ends
    group by promotion.store_type, promotion.day, promotion.promotion_id
)

select
    store_type,
    day,
    count(*) as promotions,
    count(*) filter (where wide) as at_most_branches,
    count(*) filter (where not wide) as at_some_branches,
    count(*) filter (where wide and has_restriction) as restricted,
    count(*) filter (where wide and has_min_spend) as with_min_spend
from listed_promotions
group by store_type, day
