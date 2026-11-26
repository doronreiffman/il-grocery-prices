-- Rule B5's median, as src/basket/rules.py's median works it: over `prices`, a sorted list of DECIMAL prices, not
-- empty, the middle price of an odd count, or the mean of the two middle ones of an even count. The mean is the two
-- prices' sum times 0.5, never a division: in DuckDB 1.5.6 a DECIMAL divided by a whole number is a DOUBLE. Cast to
-- three places, which holds the mean of two prices of two places exactly. DuckDB lists start at 1. `prices` is written
-- seven times, so pass a column, not an expression to work out.
{% macro median_price(prices) -%}
cast(case
    when len({{ prices }}) % 2 = 1 then {{ prices }}[len({{ prices }}) // 2 + 1]
    else ({{ prices }}[len({{ prices }}) // 2] + {{ prices }}[len({{ prices }}) // 2 + 1]) * 0.5
end as decimal(15, 3))
{%- endmacro %}
