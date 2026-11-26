-- One price file a store and day (rule B1: a store's latest file of the day; _prices.yml): one row a store and day
-- whose rows come from more than one file.
select chain, day, store, count(distinct file) as files
from {{ ref('stg_prices') }}
group by chain, day, store
having count(distinct file) > 1
