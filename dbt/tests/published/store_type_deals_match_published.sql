-- store_type_deals gives each published store page's N and M (_published.yml): one row a published store-type day whose
-- N or M is not the model's, or that the model has no row for (the macro store_page_differences), but a store page
-- known_differences lists.
select differing.*
from ({{ store_page_differences() }}) as differing
anti join {{ ref('known_differences') }} as known
    on known.kind = 'store_page'
    and known.key = differing.store_type
    and known.day = differing.day
