-- A store type's day is a hole exactly when it has no included store or fewer than half of them have a file (rule B8
-- by store type: included = 0 or with_file * 2 < included), and a promotion hole exactly when fewer than half its
-- counted stores have a promotion file or the chain's promotions were not read (rule S0: promo_files * 2 < counted or
-- a promotions error), as src/shopper/items.py writes the report (_items.yml). One row a store type and day whose flags
-- break either.
select chain, store_type, day, hole, included, with_file, promo_hole, counted, promo_files, promotions_error
from {{ ref('stg_store_type_days') }}
where hole is distinct from (included = 0 or with_file * 2 < included)
    or promo_hole is distinct from (promo_files * 2 < counted or promotions_error is not null)
