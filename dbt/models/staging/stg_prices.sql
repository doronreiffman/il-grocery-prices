-- The prices tables' rows, renamed (stg_prices.yml). The day is the folder's.
select
    chain,
    "date" as day,
    store,
    sub_chain,
    code,
    code_norm as barcode,
    gs1,
    price,
    file
from {{ source('tables', 'prices') }}
