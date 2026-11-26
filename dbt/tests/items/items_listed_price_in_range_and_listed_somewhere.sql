-- An items row's listed price is within its stores' range and above one agora, and at least one store lists the
-- product (rules P2, B4 and B5: lowest <= listed <= highest; listed above 0.01; listing at least 1; _items.yml): one
-- row an items row that breaks any of them, or that lacks one of the four figures.
select chain, store_type, day, barcode, listed, low, high, listing
from {{ ref('stg_items') }}
where not coalesce(low <= listed and listed <= high and listed > 0.01 and listing >= 1, false)
