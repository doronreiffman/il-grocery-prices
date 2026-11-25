-- The basket's prices as published, a row per chain and item (stg_published_basket.yml): the day file's map of
-- chains and each chain's map of items unnested; the published code's leading zeros stripped, as every barcode
-- match in the project strips them.
select
    chain_entry.key as chain,
    basket_day.day,
    ltrim(item_entry.key, '0') as barcode,
    item_entry.value.median as median,
    item_entry.value.low as low,
    item_entry.value.high as high,
    item_entry.value.listing as listing,
    item_entry.value.double_coded as double_coded
from {{ source('published', 'basket_days') }} as basket_day,
    unnest(map_entries(basket_day.chains)) as chains(chain_entry),
    unnest(map_entries(chain_entry.value.items)) as items(item_entry)
