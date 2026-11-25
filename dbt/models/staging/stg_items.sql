-- The items tables' rows, renamed (stg_items.yml). The day is the folder's.
select
    chain,
    "column" as store_type,
    "date" as day,
    code as barcode,
    listed,
    low,
    high,
    listing,
    wide,
    on_promotion,
    next_start,
    promotions
from {{ source('tables', 'items') }}
