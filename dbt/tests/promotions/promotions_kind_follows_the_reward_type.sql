-- A promotions row's kind is its reward type's, by the project's var kinds (rule P3: 1 and 10 n_for_m, 2 percent_off,
-- 3 fixed_price; none for any other, 0 among them), and no row is of reward type 6 or 12, a gift or a basket reward,
-- whose promotion the extraction drops whole (src/shopper/promotions.py, NOT_SHELF; _promotions.yml). One row a
-- promotions row that breaks either.
select chain, store_type, day, promotion_id, group_id, code, reward_type, kind
from {{ ref('stg_promotions') }}
where kind is distinct from (
        case reward_type
            {%- for reward_type, kind in var('kinds').items() %}
            when '{{ reward_type }}' then '{{ kind }}'
            {%- endfor %}
        end
    )
    or reward_type in ('6', '12')
