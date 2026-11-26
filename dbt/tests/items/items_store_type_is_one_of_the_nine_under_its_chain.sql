-- An items row's store type is one of the nine, under its own chain, by the project's var store_types
-- (docs/store-first.md, "The rules"; _items.yml): one row an items row whose chain is not its store type's, or whose
-- store type the var does not name.
select chain, store_type, day, barcode
from {{ ref('stg_items') }}
where chain is distinct from (
        case store_type
            {%- for store_type, store_type_chain in var('store_types').items() %}
            when '{{ store_type }}' then '{{ store_type_chain }}'
            {%- endfor %}
        end
    )
