-- promotion_reach's count at most branches, from the promotions table, is the items table's (rule P3; _across.yml):
-- the promotions on a store type's items rows that day that are wide, have a kind and run that day, each counted once
-- however many rows carry it, as src/shopper/items.py writes a row's promotions. Compared on each store-type day of
-- the items reports whose chain has a promotions row that day; a side with none counts 0. One row a store-type day
-- whose two counts differ.
with promoted_days as (
    select distinct chain, day from {{ ref('stg_promotions') }}
),

compared as (
    select report.chain, report.store_type, report.day
    from {{ ref('stg_store_type_days') }} as report
    semi join promoted_days
        on promoted_days.chain = report.chain
        and promoted_days.day = report.day
),

listed_entries as (
    select item.store_type, item.day, count(distinct entry.promotion_id) as at_most_branches
    from {{ ref('stg_items') }} as item,
        unnest(item.promotions) as entries(entry)
    where entry.wide and entry.kind is not null and entry."start" <= item.day and item.day <= entry."end"
    group by item.store_type, item.day
)

select
    compared.chain,
    compared.store_type,
    compared.day,
    reach.at_most_branches as reach_at_most_branches,
    listed_entries.at_most_branches as items_at_most_branches
from compared
left join {{ ref('promotion_reach') }} as reach
    on reach.store_type = compared.store_type
    and reach.day = compared.day
left join listed_entries
    on listed_entries.store_type = compared.store_type
    and listed_entries.day = compared.day
where coalesce(reach.at_most_branches, 0) is distinct from coalesce(listed_entries.at_most_branches, 0)
