-- Each published day known_differences lists has both sides and still differs in some figure (docs/dbt-layer.md,
-- section 3, "The three that fail today", 2; _published.yml). The comparisons skip a listed day whole, so a further
-- difference on it stays unseen while it is listed; and this test proves only that each listed day still differs in
-- some figure, so a day whose stated reason is gone stays listed while it differs for another reason. The differences
-- are the comparisons' own (the macros in dbt/macros/published_differences.sql), before any listed day is skipped, and
-- each is read from a published page or basket's day, a basket's on a chain-day the day file names with a prices table
-- alone: a listed day with no published side, or a basket day with no prices table, has none. A store page differs
-- when its N, M, a shown row or its promotions count is not the model's, and a published page with no store_type_deals
-- row is one; so a listed store page must have that row as well. One row a listed day that lacks a side or no longer
-- differs.
with modelled_pages as (
    select store_type, day from {{ ref('store_type_deals') }}
),

differing_pages as (
    select store_type, day from ({{ store_page_differences() }})
    union
    select store_type, day from ({{ shown_row_differences() }})
    union
    select store_type, day from ({{ promotion_count_differences() }})
),

differing_baskets as (
    select distinct chain, day from ({{ basket_differences() }})
)

select
    page.kind,
    page.key,
    page.day,
    page_modelled.day is not null as modelled,
    page_differing.day is not null as differs
from {{ ref('known_differences') }} as page
left join modelled_pages as page_modelled
    on page_modelled.store_type = page.key
    and page_modelled.day = page.day
left join differing_pages as page_differing
    on page_differing.store_type = page.key
    and page_differing.day = page.day
where page.kind = 'store_page'
    and (page_modelled.day is null or page_differing.day is null)

union all

select
    basket.kind,
    basket.key,
    basket.day,
    null as modelled,
    basket_differing.day is not null as differs
from {{ ref('known_differences') }} as basket
left join differing_baskets as basket_differing
    on basket_differing.chain = basket.key
    and basket_differing.day = basket.day
where basket.kind = 'basket'
    and basket_differing.day is null
