-- Is this promotion a deal, at this store type, today? (product_deals.yml): src/shopper/verdict.py's S2 and S4 over
-- int_day_prices, for the covered products (P1), with the front list's bar.
with days as (
    select store_type, barcode, day, wide, hole, tracked, on_sale, sale_price, day_price
    from {{ ref('int_day_prices') }}
),

covered as (
    -- P1: the first day each product is wide at some store type, on a day with no hole there.
    select barcode, min(day) as since
    from days
    where wide and not hole
    group by barcode
),

today as (
    -- A row for each tracked day of a covered product on which a promotion counts (S0, S3).
    select d.store_type, d.barcode, d.day, d.sale_price as today_price
    from days as d
    join covered as c on c.barcode = d.barcode and c.since <= d.day
    where d.tracked and d.sale_price is not null
),

history as (
    -- The same store type's and product's rows of the read_days days before the day, the day itself left out.
    select
        t.store_type,
        t.barcode,
        t.day,
        t.today_price,
        h.day as seen,
        not h.hole as recorded,
        h.tracked,
        h.tracked and h.on_sale as on_sale,
        h.tracked and h.day_price is not null as priced,
        h.tracked and h.day_price is null as unknown,
        h.day_price
    from today as t
    left join days as h
        on h.store_type = t.store_type
        and h.barcode = t.barcode
        and h.day between t.day - {{ var('read_days') }} and t.day - 1
),

counted as (
    select
        store_type,
        barcode,
        day,
        today_price,
        count(*) filter (where tracked) as days_tracked,
        count(*) filter (where priced) as days_priced,
        count(*) filter (where on_sale) as days_on_sale,
        count(*) filter (where unknown) as days_unknown,
        -- The bar's window: the recent_days days before the day, a promotion hole being a record.
        count(*) filter (where recorded and seen >= day - {{ var('recent_days') }}) as days_recorded,
        list_sort(list(day_price) filter (where priced)) as prices
    from history
    group by store_type, barcode, day, today_price
),

middled as (
    -- S2: the middle of the sorted day prices, the higher middle of an even count (lists count from 1).
    select *, prices[len(prices) // 2 + 1] as middle_price
    from counted
),

judged as (
    -- S4: no verdict with no day price or with more than half the tracked days of unknown price.
    select
        *,
        case
            when days_priced = 0 or 2 * days_unknown > days_tracked then 'no verdict'
            when middle_price - today_price >= {{ var('deal_min') }} then 'deal'
            else 'no deal'
        end as verdict
    from middled
)

select
    store_type,
    barcode,
    day,
    today_price,
    -- As on the site, only a deal or no deal has a usual price and a saving (S4).
    case when verdict <> 'no verdict' then middle_price end as usual_price,
    case when verdict <> 'no verdict' then middle_price - today_price end as saving,
    days_tracked,
    days_priced,
    days_on_sale,
    days_unknown,
    days_recorded,
    days_recorded >= {{ var('min_front_days') }} as checked,
    verdict
from judged
