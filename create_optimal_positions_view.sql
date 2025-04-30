-- Create view for optimal positions with product variant as primary key
CREATE VIEW ats_wms_optimal_positions AS
SELECT 
    op.POSITION_ID,
    op.POSITION_NAME,
    op.POSITION_NUMBER_IN_RACK,
    op.RACK_ID,
    op.AREA_ID,
    op.FLOOR_ID,
    cs.PRODUCT_VARIANT_CODE,
    cs.PRODUCT_VARIANT_NAME,
    cs.PRODUCT_NAME,
    op.POSITION_IS_EMPTY,
    op.POSITION_IS_ALLOCATED,
    op.POSITION_IS_ACTIVE,
    op.proximity_score,
    op.nearby_products
FROM 
    (
        -- This subquery will contain the optimal positions data
        -- with their proximity scores and nearby products
        SELECT 
            mp.POSITION_ID,
            mp.POSITION_NAME,
            mp.POSITION_NUMBER_IN_RACK,
            mp.RACK_ID,
            mp.AREA_ID,
            mp.FLOOR_ID,
            mp.POSITION_IS_EMPTY,
            mp.POSITION_IS_ALLOCATED,
            mp.POSITION_IS_ACTIVE,
            -- These columns will be populated from the optimal positions analysis
            NULL as proximity_score,
            NULL as nearby_products
        FROM 
            ats_wms_master_position_details mp
        WHERE 
            mp.POSITION_IS_ACTIVE = 1
            AND mp.POSITION_IS_DELETED = 0
    ) op
LEFT JOIN 
    ats_wms_current_stock_details cs ON op.POSITION_ID = cs.POSITION_ID
WHERE 
    op.POSITION_IS_EMPTY = 1
    AND op.POSITION_IS_ALLOCATED = 0; 