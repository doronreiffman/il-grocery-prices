-- The price rows that count (int_counted_prices.yml): rule B2's stores and sub-chains left out by number, each at its
-- own chain, and rule B4's floor. Two anti-joins on equalities alone, one on chain and store, one on chain and
-- sub-chain, so each is a hash join (docs/dbt-layer.md, "Left to the builder": keeping the left-out filter cheap). A
-- NULL sub-chain equals nothing, so a row with no sub-chain meets no left-out sub-chain, as B2 says; a NULL price is
-- not above the floor.
with left_out_store as (
    select chain, key as store from {{ ref('left_out_stores') }} where kind = 'store'
),

left_out_sub_chain as (
    select chain, key as sub_chain from {{ ref('left_out_stores') }} where kind = 'sub_chain'
)

select
    prices.chain,
    prices.day,
    prices.store,
    prices.sub_chain,
    prices.code,
    prices.barcode,
    prices.gs1,
    prices.price,
    prices.file
from {{ ref('stg_prices') }} as prices
anti join left_out_store
    on left_out_store.chain = prices.chain and left_out_store.store = prices.store
anti join left_out_sub_chain
    on left_out_sub_chain.chain = prices.chain and left_out_sub_chain.sub_chain = prices.sub_chain
where prices.price > 0.01
