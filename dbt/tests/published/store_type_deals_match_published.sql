-- store_type_deals gives each published store page's N and M (_published.yml): one row a published store-type day whose
-- N or M is not the model's, or that the model has no row for (the macro store_page_differences), but a store page
-- known_differences lists (the macro without_known_store_pages).
{{ without_known_store_pages(store_page_differences()) }}
