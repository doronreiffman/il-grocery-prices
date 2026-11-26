-- Each chain's price on each day for the basket's products (basket_prices.yml): rule B5 over the price rows that
-- count, as src/basket/rules.py works it (store_prices_sql, chain_prices): one price a store, then the chain's median,
-- lowest and highest over its stores. Each product's store prices are listed, then the list sorted, as the Python
-- does it.
with basket as (
    -- The basket's codes, their leading zeros stripped, as every barcode match in the project strips them.
    select ltrim(item.code, '0') as barcode
    from {{ source('repo', 'basket') }} as basket_file,
        unnest(basket_file.items) as listed(item)
),

store_prices as (
    -- One price a store: its lowest over its rows of the product, and how many codes it lists the product under
    -- (more than one: a double-coded store).
    select chain, day, barcode, store, min(price) as price, count(*) as codes
    from {{ ref('int_counted_prices') }}
    where barcode in (select barcode from basket)
    group by chain, day, barcode, store
),

chain_prices as (
    select
        chain,
        day,
        barcode,
        list_sort(list(price)) as prices,
        count(*) as stores_listing,
        count(*) filter (where codes > 1) as double_coded
    from store_prices
    group by chain, day, barcode
)

select
    chain,
    day,
    barcode,
    {{ median_price('prices') }} as median,
    prices[1] as low,
    prices[-1] as high,
    stores_listing,
    double_coded
from chain_prices
