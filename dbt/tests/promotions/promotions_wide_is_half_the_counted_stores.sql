-- A promotions row is wide when at least half the store type's counted stores carry it on the code (rule P3, by store
-- type: stores * 2 >= counted), and its counts are in order: 1 <= stores <= promotion stores <= counted
-- (_promotions.yml). One row a promotions row that breaks either.
select chain, store_type, day, promotion_id, group_id, code, stores, promotion_stores, counted, wide
from {{ ref('stg_promotions') }}
where wide is distinct from (stores * 2 >= counted)
    or not coalesce(1 <= stores and stores <= promotion_stores and promotion_stores <= counted, false)
