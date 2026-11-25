-- The stores and sub-chains rule B2 leaves out by number (left_out_stores.yml), one row a line;
-- tests/test_dbt_project.py reads the rows from these lines and holds them equal to basket.chains.EXCLUDED.
select chain, kind, key
from (values
    ('shufersal', 'sub_chain', '5'),
    ('shufersal', 'store', '413'),
    ('ramilevy', 'store', '39'),
    ('carrefour', 'store', '471')
) as left_out (chain, kind, key)
