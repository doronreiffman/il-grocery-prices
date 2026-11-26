-- The tables' GS1 flag is the check digit's (src/basket/barcode.py's is_gs1, worked again in SQL by the macro is_gs1;
-- _prices.yml): one row a barcode and flag that disagree. The rule is worked once a barcode and flag, not once a row.
with flagged as (
    select distinct barcode, gs1
    from {{ ref('stg_prices') }}
)

select barcode, gs1
from flagged
where gs1 is distinct from {{ is_gs1('barcode') }}
