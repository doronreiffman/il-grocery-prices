-- Each price row comes from a full price file of its own day (rule B1; _prices.yml): one row a file whose stored name
-- is not a PriceFull name of the table's day. A name is read as src/collector/names.py reads one: the kind in any
-- case, the chain's 13 digits, one or more groups (the store last), the day, a time, .gz or .xml; and a conflict
-- copy's dot and 12 hex digits after it, as src/collector/store.py's published_name drops them. The names are matched
-- once a file, not once a row.
with files as (
    select chain, day, file, count(*) as price_rows
    from {{ ref('stg_prices') }}
    group by chain, day, file
)

select chain, day, file, price_rows
from files
where not coalesce(regexp_full_match(
    file,
    '(?i:pricefull)[0-9]{13}(-[0-9]{1,4})+-' || strftime(day, '%Y%m%d') || '([0-9]{4})?(-[0-9]+)?(?i:\.gz|\.xml)?(\.[0-9a-f]{12})?'
), false)
