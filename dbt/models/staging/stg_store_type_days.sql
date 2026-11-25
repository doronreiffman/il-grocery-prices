-- The items reports' counts and flags, a row per store type (stg_store_type_days.yml): the report's map of store
-- types unnested. The day is the folder's, never the report's own day field.
select
    report.chain,
    entry.key as store_type,
    report."date" as day,
    entry.value.hole as hole,
    entry.value.promo_hole as promo_hole,
    entry.value.included as included,
    entry.value.with_file as with_file,
    entry.value.counted as counted,
    entry.value.promo_files as promo_files,
    entry.value.items as items,
    entry.value.wide as wide,
    entry.value.on_promotion as on_promotion,
    entry.value.valid_deals as valid_deals,
    report.promotions_error
from {{ source('tables', 'items_reports') }} as report,
    unnest(map_entries(report."columns")) as store_types(entry)
