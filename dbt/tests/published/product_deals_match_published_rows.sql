-- product_deals gives each row a published store page shows: today's price, the usual price, the saving and the days
-- with a day price (_published.yml): one row a shown row that is not the model's, or that the model has no row for (the
-- macro shown_row_differences), but on a store page known_differences lists.
select differing.*
from ({{ shown_row_differences() }}) as differing
anti join {{ ref('known_differences') }} as known
    on known.kind = 'store_page'
    and known.key = differing.store_type
    and known.day = differing.day
