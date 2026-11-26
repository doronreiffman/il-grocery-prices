-- Each items report's counts are its table's own, for every store type and day the report holds: the rows, those wide,
-- those on promotion, and the promotions on them running that day whose deal is valid, wide or not
-- (src/shopper/items.py's ColumnReport; _items.yml). The rows meet their report on chain, store type and day, so a row
-- under a store type the report lacks is left out. One row a store type and day whose report and table differ.
with counted as (
    select
        report.chain,
        report.store_type,
        report.day,
        report.items,
        report.wide,
        report.on_promotion,
        report.valid_deals,
        count(item.barcode) as table_items,
        count(item.barcode) filter (where item.wide) as table_wide,
        count(item.barcode) filter (where item.on_promotion) as table_on_promotion,
        coalesce(sum(len([p for p in item.promotions
                          if p.valid and p."start" <= item.day and item.day <= p."end"])), 0) as table_valid_deals
    from {{ ref('stg_store_type_days') }} as report
    left join {{ ref('stg_items') }} as item
        on item.chain = report.chain
        and item.store_type = report.store_type
        and item.day = report.day
    group by report.chain, report.store_type, report.day, report.items, report.wide, report.on_promotion,
        report.valid_deals
)

select *
from counted
where items is distinct from table_items
    or wide is distinct from table_wide
    or on_promotion is distinct from table_on_promotion
    or valid_deals is distinct from table_valid_deals
