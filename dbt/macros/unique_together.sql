-- A data test that a relation holds one row per key: over `model`, the groups of `columns` (a list of column names,
-- quoted where SQL needs it) with more than one row, one returned per repeated key, with its rows' count.
{% test unique_together(model, columns) %}
select {{ columns | join(', ') }}, count(*) as copies
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}
