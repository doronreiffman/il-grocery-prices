-- The published days today's tables no longer give (known_differences.yml), a row each from the var
-- known_differences; a reason's ' doubled, so any reason is SQL text. An empty list gives no row, its columns typed.
{%- set listed = var('known_differences') %}
{%- if listed %}
select kind, key, cast(day as date) as day, reason
from (values
{%- for difference in listed %}
    ('{{ difference.kind }}', '{{ difference.key }}', '{{ difference.day }}', '{{ difference.reason | replace("'", "''") }}'){{ "," if not loop.last }}
{%- endfor %}
) as listed (kind, key, day, reason)
{%- else %}
select
    cast(null as varchar) as kind,
    cast(null as varchar) as key,
    cast(null as date) as day,
    cast(null as varchar) as reason
where false
{%- endif %}
