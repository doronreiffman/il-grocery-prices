-- The models against the files the site published (docs/dbt-layer.md, section 3, "Against the published files"): each
-- macro gives the published rows that differ from the model's, before any known difference is skipped, so the
-- comparisons (dbt/tests/published/) and known_differences_still_differ read the same differences.

-- The store pages whose N or M is not store_type_deals', or that it has no row for: one row a published store-type day.
{% macro store_page_differences() -%}
select
    page.store_type,
    page.day,
    page.deals as published_deals,
    page.checked as published_checked,
    model.deals,
    model.checked
from {{ ref('stg_published_store_pages') }} as page
left join {{ ref('store_type_deals') }} as model
    on model.store_type = page.store_type
    and model.day = page.day
where page.deals is distinct from model.deals
    or page.checked is distinct from model.checked
{%- endmacro %}

-- The rows a store page shows whose today's price, usual price, saving or days are not product_deals', or that it has
-- no row for: one row a shown row. The prices are compared as the site writes them, text with two places; the days are
-- the days with a day price (src/shopper/siteday.py writes len(found.priced)).
{% macro shown_row_differences() -%}
select
    shown.store_type,
    shown.day,
    shown.barcode,
    shown.today,
    shown.usual,
    shown.saving,
    shown.days,
    deal.today_price,
    deal.usual_price,
    deal.saving as model_saving,
    deal.days_priced
from (
    select page.store_type, page.day, shown_row.barcode, shown_row.today, shown_row.usual, shown_row.saving,
        shown_row.days
    from {{ ref('stg_published_store_pages') }} as page,
        unnest(page.shown_rows) as listed(shown_row)
) as shown
left join {{ ref('product_deals') }} as deal
    on deal.store_type = shown.store_type
    and deal.day = shown.day
    and deal.barcode = shown.barcode
where shown.today is distinct from cast(deal.today_price as varchar)
    or shown.usual is distinct from cast(deal.usual_price as varchar)
    or shown.saving is distinct from cast(deal.saving as varchar)
    or shown.days is distinct from deal.days_priced
{%- endmacro %}

-- The store pages whose promotions count, the promotions line's number (src/shopper/build.py, _today), is not
-- promotion_reach's count at most branches: one row a published store-type day. Compared on a store-type day of the
-- items reports that is no hole and no promotion hole, where the site counts no promotion and publishes no count, and
-- whose chain has a promotions row that day (docs/dbt-layer-plan.md, decision 17: with none there is no promotions table
-- to count from); a store type with no promotion_reach row that day counts 0.
{% macro promotion_count_differences() -%}
with promoted_days as (
    select distinct chain, day from {{ ref('stg_promotions') }}
)

select
    report.chain,
    page.store_type,
    page.day,
    page.promotions,
    reach.at_most_branches
from {{ ref('stg_published_store_pages') }} as page
join {{ ref('stg_store_type_days') }} as report
    on report.store_type = page.store_type
    and report.day = page.day
semi join promoted_days
    on promoted_days.chain = report.chain
    and promoted_days.day = report.day
left join {{ ref('promotion_reach') }} as reach
    on reach.store_type = page.store_type
    and reach.day = page.day
where not report.hole
    and not report.promo_hole
    and page.promotions is distinct from coalesce(reach.at_most_branches, 0)
{%- endmacro %}

-- A store page's differences, `differences` (the SQL of one of the macros above), but on the store pages
-- known_differences lists: the skip all three store-page comparisons share.
{% macro without_known_store_pages(differences) -%}
select differing.*
from ({{ differences }}) as differing
anti join {{ ref('known_differences') }} as known
    on known.kind = 'store_page'
    and known.key = differing.store_type
    and known.day = differing.day
{%- endmacro %}

-- The basket items whose median, lowest, highest, stores listing or double-coded stores the day file and basket_prices
-- do not give alike, on the chain-days the day files publish that the prices table has: one row a chain, day and item,
-- published, priced or both. A chain-day is published when the day file names the chain, a key of its chains, with an
-- item or with none, so the compared chain-days are read from the day files themselves, not from their items. The site
-- publishes every basket item with a price at the chain that day (src/basket/rules.py, price_basket's `listed`), so an
-- item on one side alone differs, a priced item at a chain the day file names with no item among them. The median is
-- rounded half up to two places, as src/basket/record.py's money rounds it, and every price is compared as the site
-- writes it, text with two places. A chain-day with no prices table is not compared: each run of the sync
-- (scripts/sync.sh) brings the prices tables of the one day it is given, so a published day may have none.
{% macro basket_differences() -%}
with compared_days as (
    select distinct listed.chain, listed.day
    from (
        select basket_day.day, unnest(map_keys(basket_day.chains)) as chain
        from {{ source('published', 'basket_days') }} as basket_day
    ) as listed
    semi join (select distinct chain, day from {{ ref('stg_prices') }}) as priced
        on priced.chain = listed.chain
        and priced.day = listed.day
),

published as (
    select item.*
    from {{ ref('stg_published_basket') }} as item
    semi join compared_days
        on compared_days.chain = item.chain
        and compared_days.day = item.day
),

basket as (
    select model.*
    from {{ ref('basket_prices') }} as model
    semi join compared_days
        on compared_days.chain = model.chain
        and compared_days.day = model.day
)

select
    coalesce(published.chain, basket.chain) as chain,
    coalesce(published.day, basket.day) as day,
    coalesce(published.barcode, basket.barcode) as barcode,
    published.median as published_median,
    published.low as published_low,
    published.high as published_high,
    published.listing as published_listing,
    published.double_coded as published_double_coded,
    basket.median,
    basket.low,
    basket.high,
    basket.stores_listing,
    basket.double_coded
from published
full join basket
    on basket.chain = published.chain
    and basket.day = published.day
    and basket.barcode = published.barcode
where published.median is distinct from cast(round(basket.median, 2) as varchar)
    or published.low is distinct from cast(basket.low as varchar)
    or published.high is distinct from cast(basket.high as varchar)
    or published.listing is distinct from basket.stores_listing
    or published.double_coded is distinct from basket.double_coded
{%- endmacro %}

-- The basket's differences at the chains `chains` keeps (SQL over the alias differing), but the basket days
-- known_differences lists.
{% macro basket_compared(chains) -%}
select differing.*
from ({{ basket_differences() }}) as differing
anti join {{ ref('known_differences') }} as known
    on known.kind = 'basket'
    and known.key = differing.chain
    and known.day = differing.day
where {{ chains }}
{%- endmacro %}
