-- The carrying stores' discounted prices are in order, lowest <= median <= highest, or all three none (no store's
-- price read); and the counts of stores priced are on percent off alone, in order there: 0 <= agrees_with_store <=
-- with_store_price <= stores (docs/shopper-site.md, "Changed after the survey", 5; src/shopper/promos.py;
-- _promotions.yml). One row a promotions row that breaks either.
select chain, store_type, day, promotion_id, group_id, code, kind, discounted_low, discounted_median, discounted_high,
    with_store_price, agrees_with_store, stores
from {{ ref('stg_promotions') }}
where not coalesce(
        discounted_low <= discounted_median and discounted_median <= discounted_high,
        discounted_low is null and discounted_median is null and discounted_high is null
    )
    or case
        when kind = 'percent_off'
            then not coalesce(
                0 <= agrees_with_store and agrees_with_store <= with_store_price and with_store_price <= stores, false
            )
        else with_store_price is not null or agrees_with_store is not null
    end
