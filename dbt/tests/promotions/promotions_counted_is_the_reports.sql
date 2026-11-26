-- A promotions row's counted stores are its store type's in the items report of its chain and day (rule P3: the
-- stores counted are P2's; _promotions.yml): one row a promotions row whose counted is not the report's, or whose store
-- type and day the report does not hold.
select
    promotion.chain,
    promotion.store_type,
    promotion.day,
    promotion.promotion_id,
    promotion.group_id,
    promotion.code,
    promotion.counted,
    report.counted as reported
from {{ ref('stg_promotions') }} as promotion
left join {{ ref('stg_store_type_days') }} as report
    on report.chain = promotion.chain
    and report.store_type = promotion.store_type
    and report.day = promotion.day
where promotion.counted is distinct from report.counted
