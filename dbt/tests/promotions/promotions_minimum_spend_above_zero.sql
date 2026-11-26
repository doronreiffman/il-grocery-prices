-- A minimum spend, when a promotions row states one, is above zero (docs/shopper-site.md, "Changed after the survey":
-- the largest MinPurchaseAmount above zero; _promotions.yml): one row a promotions row whose minimum spend is zero or
-- below.
select chain, store_type, day, promotion_id, group_id, code, min_spend
from {{ ref('stg_promotions') }}
where min_spend <= 0
