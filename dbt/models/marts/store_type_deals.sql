-- At each store type today, how many of the promotions are deals? (store_type_deals.yml): the store page's M and N,
-- and how often the M were on sale, for every store type and day of the items reports.
select
    d.store_type,
    d.day,
    count(p.barcode) filter (where p.checked) as checked,
    count(p.barcode) filter (where p.checked and p.verdict = 'deal') as deals,
    count(p.barcode) filter (where p.checked and p.days_tracked > 0 and p.days_on_sale = p.days_tracked)
        as on_sale_every_tracked_day,
    count(p.barcode) filter (where p.checked and 2 * p.days_on_sale > p.days_tracked) as on_sale_more_than_half
from {{ ref('stg_store_type_days') }} as d
left join {{ ref('product_deals') }} as p on p.store_type = d.store_type and p.day = d.day
group by d.store_type, d.day
