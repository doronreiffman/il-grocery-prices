-- The store pages' numbers as published, a row per store type with a front block (stg_published_store_pages.yml):
-- the site-day file's map of store types unnested.
select
    entry.key as store_type,
    site_day.day,
    entry.value.front.deals as deals,
    entry.value.front.checked as checked,
    entry.value.front.promotions as promotions,
    entry.value.front.products as products,
    entry.value.front."rows" as shown_rows
from {{ source('published', 'site_days') }} as site_day,
    unnest(map_entries(site_day."columns")) as store_types(entry)
where entry.value.front is not null
