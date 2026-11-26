-- Each price row comes from a full price file of its own day (rule B1; _prices.yml): one row a file whose stored name
-- is not a PriceFull name of the table's day. A name is read as src/collector/names.py reads one: the kind in any
-- case, the chain's 13 digits, one or more groups (the store last), the day, a time, .gz or .xml; and a conflict
-- copy's dot and 12 hex digits after it, as src/collector/store.py's published_name drops them. The name's day is
-- read with a pattern that never changes, then compared with the table's day: DuckDB runs this filter below the
-- group-by, once a row, and a pattern built from each row's day would be compiled again for every price row
-- (tests/test_dbt_project.py, the literal patterns). The name's day is the eight digits after the first dash that
-- more than four digits follow, since a group has one to four; a name that is no PriceFull name gives no day.
with files as (
    select chain, day, file, count(*) as price_rows
    from {{ ref('stg_prices') }}
    group by chain, day, file
)

select chain, day, file, price_rows
from files
where regexp_extract(
    file,
    '^(?i:pricefull)[0-9]{13}(?:-[0-9]{1,4})+-([0-9]{8})(?:[0-9]{4})?(?:-[0-9]+)?(?i:\.gz|\.xml)?(?:\.[0-9a-f]{12})?$',
    1
) is distinct from strftime(day, '%Y%m%d')
