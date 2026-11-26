-- At each chain of one store type (the var store_types), the items table's listed price, lowest and highest price and
-- stores listing are rule B5 worked again from the prices table's rows that count (int_counted_prices), GS1 codes
-- alone, as src/shopper/items.py works them over the store type's stores (P2): one price a store, its lowest over the
-- codes with the same digits, then the median, the lowest and the highest over the stores (_across.yml). Both ways, on
-- the chain-days both tables have. One row a chain, day and barcode whose figures differ, or that one side lacks.
with one_store_type as (
    select chain
    from (values
        {%- for store_type, store_type_chain in var('store_types').items() %}
        ('{{ store_type }}', '{{ store_type_chain }}'){{ "," if not loop.last }}
        {%- endfor %}
    ) as store_types (store_type, chain)
    group by chain
    having count(*) = 1
),

store_prices as (
    select prices.chain, prices.day, prices.barcode, prices.store, min(prices.price) as price
    from {{ ref('int_counted_prices') }} as prices
    semi join one_store_type on one_store_type.chain = prices.chain
    where prices.gs1
    group by prices.chain, prices.day, prices.barcode, prices.store
),

worked as (
    select
        chain,
        day,
        barcode,
        list_sort(list(price)) as prices,
        min(price) as low,
        max(price) as high,
        count(*) as listing
    from store_prices
    group by chain, day, barcode
),

item_rows as (
    select item.chain, item.day, item.barcode, item.listed, item.low, item.high, item.listing
    from {{ ref('stg_items') }} as item
),

-- The items rows of the chain-days with worked figures, so of the chains of one store type alone, and the worked
-- figures of the chain-days with items rows.
items as (
    select item_rows.*
    from item_rows
    semi join (select distinct chain, day from worked) as priced
        on priced.chain = item_rows.chain
        and priced.day = item_rows.day
),

figures as (
    select worked.chain, worked.day, worked.barcode, {{ median_price('worked.prices') }} as listed, worked.low,
        worked.high, worked.listing
    from worked
    semi join (select distinct chain, day from item_rows) as listed_days
        on listed_days.chain = worked.chain
        and listed_days.day = worked.day
)

select
    coalesce(items.chain, figures.chain) as chain,
    coalesce(items.day, figures.day) as day,
    coalesce(items.barcode, figures.barcode) as barcode,
    items.listed,
    figures.listed as worked_listed,
    items.low,
    figures.low as worked_low,
    items.high,
    figures.high as worked_high,
    items.listing,
    figures.listing as worked_listing
from items
full join figures
    on figures.chain = items.chain
    and figures.day = items.day
    and figures.barcode = items.barcode
where items.listed is distinct from figures.listed
    or items.low is distinct from figures.low
    or items.high is distinct from figures.high
    or items.listing is distinct from figures.listing
