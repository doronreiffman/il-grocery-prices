-- Every chain has an items table on every day from its own first day to the last day any chain has (no rule states it:
-- a missing table is a day not extracted; docs/dbt-layer.md, section 3; _items.yml): one row a chain and day with no
-- items row. A warning, not an error.
with days as (
    select distinct chain, day
    from {{ ref('stg_items') }}
),

spans as (
    select chain, min(day) as first_day, (select max(day) from days) as last_day
    from days
    group by chain
),

expected as (
    select chain, cast(unnest(generate_series(first_day, last_day, interval 1 day)) as date) as day
    from spans
)

select expected.chain, expected.day
from expected
left join days
    on days.chain = expected.chain
    and days.day = expected.day
where days.day is null
