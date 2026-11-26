-- src/basket/barcode.py's is_gs1 in SQL, over `barcode`, a code with its leading zeros stripped (the tables'
-- code_norm): true when it has 8 to 14 ASCII digits, the first not a zero, and its last digit is the GS1 check digit:
-- counting left from that digit, the digits are weighted 3, 1, 3, 1, ..., and the weighted sum plus the check digit
-- ends in 0. False for anything else, NULL included. The digits before the check digit are read reversed, so place 1,
-- the first of a DuckDB list, is the one next to it. `barcode` is written four times, so pass a column.
{% macro is_gs1(barcode) -%}
coalesce(
    regexp_full_match({{ barcode }}, '[1-9][0-9]{7,13}')
    and (
        list_sum([
            try_cast(digit as integer) * (case when place % 2 = 1 then 3 else 1 end)
            for digit, place in string_split(reverse(substr({{ barcode }}, 1, len({{ barcode }}) - 1)), '')
        ])
        + try_cast(right({{ barcode }}, 1) as integer)
    ) % 10 = 0,
    false
)
{%- endmacro %}
