-- An items row's on_promotion is true exactly when a promotion on the row is wide, has a kind and runs that day (start
-- <= day <= end), whether its deal is valid or not, as src/shopper/items.py works it (rule P3); and it is NULL exactly
-- when the chain's promotions were not read, which the items report of the row's chain, store type and day says by
-- its promotions error (_items.yml). One row an items row that breaks either. A row under a store type the report
-- lacks meets no report and is the store-type test's.
select item.chain, item.store_type, item.day, item.barcode, item.on_promotion, report.promotions_error
from {{ ref('stg_items') }} as item
join {{ ref('stg_store_type_days') }} as report
    on report.chain = item.chain
    and report.store_type = item.store_type
    and report.day = item.day
where case
        when report.promotions_error is not null then item.on_promotion is not null
        else item.on_promotion is distinct from (
            len([p for p in item.promotions
                 if p.wide and p.kind is not null and p."start" <= item.day and item.day <= p."end"]) > 0
        )
    end
