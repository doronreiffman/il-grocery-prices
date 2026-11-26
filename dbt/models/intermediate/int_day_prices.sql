-- Each store type's price for each product on each day it lists it (int_day_prices.yml): S3's lowest promotion that
-- counts, S1's day price and S0's tracked day, as src/shopper/verdict.py works them. Built as a table:
-- product_deals reads it for its rows, their coverage and their history.
{{ config(materialized='table') }}

with items as (
    -- An items table's row with its report's flags; a table with no report beside it is no table (shopper.history).
    select
        i.chain,
        i.store_type,
        i.barcode,
        i.day,
        i.wide,
        i.listed,
        i.on_promotion,
        i.promotions,
        d.hole,
        d.promo_hole
    from {{ ref('stg_items') }} as i
    join {{ ref('stg_store_type_days') }} as d
        on d.chain = i.chain and d.store_type = i.store_type and d.day = i.day
),

priced as (
    select
        chain,
        store_type,
        barcode,
        day,
        wide,
        round(listed, 2) as listed_shown,
        -- S3: a promotion counts when it is wide, valid, has a kind and runs that day; its price is to the agora.
        list_min([p.price for p in promotions
                  if p.wide and p.valid and p.kind is not null and p."start" <= day and day <= p."end"]) as sale_price,
        coalesce(on_promotion, false) as on_sale,
        hole,
        promo_hole,
        not hole and not promo_hole as tracked
    from items
)

select
    chain,
    store_type,
    barcode,
    day,
    wide,
    listed_shown,
    sale_price,
    on_sale,
    hole,
    promo_hole,
    tracked,
    -- S1: on sale with no promotion that counts is a sale day of unknown price, with no day price.
    case
        when sale_price is not null then least(listed_shown, sale_price)
        when on_sale then null
        else listed_shown
    end as day_price
from priced
