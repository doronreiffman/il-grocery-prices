-- promotion_reach's count at most branches gives each published store page's promotions count, the promotions line's
-- number (src/shopper/build.py, _today; _published.yml). Compared on a published store-type day of the items reports
-- that is no hole and no promotion hole, where the site counts no promotion and publishes no count, and whose chain has
-- a promotions row that day (docs/dbt-layer-plan.md, decision 17: with none there is no promotions table to count
-- from); a store type with no promotion_reach row that day counts 0. One row a store-type day whose two counts differ.
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
