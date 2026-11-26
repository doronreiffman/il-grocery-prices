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

-- The published basket items whose median, lowest, highest, stores listing or double-coded stores are not
-- basket_prices', or that it has no row for, on the chain-days the prices table has: one row a published chain, day and
-- item. The median is rounded half up to two places, as src/basket/record.py's money rounds it, and every price is
-- compared as the site writes it, text with two places. A chain-day with no prices table is not compared: each run of
-- the sync (scripts/sync.sh) brings the prices tables of the one day it is given, so a published day may have none.
{% macro basket_differences() -%}
select
    published.chain,
    published.day,
    published.barcode,
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
from {{ ref('stg_published_basket') }} as published
semi join (select distinct chain, day from {{ ref('stg_prices') }}) as priced
    on priced.chain = published.chain
    and priced.day = published.day
left join {{ ref('basket_prices') }} as basket
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
