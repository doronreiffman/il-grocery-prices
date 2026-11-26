-- An items row is wide exactly when the stores listing the product are at least half its store type's stores with a
-- file, from the items report of its chain, store type and day (rule B6 by store type, P1: listing * 2 >= with_file,
-- src/basket/rules.py's covers; _items.yml): one row an items row whose wide is not that. A row under a store type the
-- report lacks meets no report and is the store-type test's.
select item.chain, item.store_type, item.day, item.barcode, item.listing, report.with_file, item.wide
from {{ ref('stg_items') }} as item
join {{ ref('stg_store_type_days') }} as report
    on report.chain = item.chain
    and report.store_type = item.store_type
    and report.day = item.day
where item.wide is distinct from (item.listing * 2 >= report.with_file)
