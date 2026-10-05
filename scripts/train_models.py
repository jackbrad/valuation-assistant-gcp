"""Train all BQML models in BigQuery: Market Index (ARIMA+), Comp Ranker, Adjustment Grids, and AVM."""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config.loader
from config.loader import settings
from google.cloud import bigquery
from google.api_core.exceptions import NotFound


def train_bqml_models():
    project_id = settings["project"]["project_id"]
    bq_loc = settings["project"]["bq_location"]
    client = bigquery.Client(project=project_id, location=bq_loc)
    v = "v1"

    print(f"=== Training BQML Model Suite on {project_id} ({bq_loc}) ===")

    # 1. Base training views
    print("\n[1/6] Creating training views (sales_features, ppsf_monthly)...")
    sql_base = f"""
    CREATE OR REPLACE VIEW `{project_id}.val_ml.sales_features` AS
    SELECT s.sale_id, s.property_id, s.sale_date, DATE_TRUNC(s.sale_date, MONTH) AS sale_month,
           CAST(s.price AS FLOAT64) AS price, s.sale_type, s.was_listed, s.estimate_shown_before_list,
           f.* EXCEPT(property_id, fact_ids, has_held_value_fact, built_at)
    FROM `{project_id}.val_core.sales` s
    JOIN `{project_id}.val_core.property_features` f USING (property_id)
    WHERE s.sale_type IN ('arms_length', 'off_market');

    CREATE OR REPLACE TABLE `{project_id}.val_ml.ppsf_monthly` AS
    SELECT submarket, sale_month AS month,
           APPROX_QUANTILES(price / gla_sqft, 100)[OFFSET(50)] AS median_ppsf,
           COUNT(*) AS n_sales
    FROM `{project_id}.val_ml.sales_features`
    GROUP BY submarket, month;
    """
    job = client.query(sql_base)
    job.result()
    print("  + Base views ready.")

    # 2. Market Index ARIMA_PLUS
    print("\n[2/6] Checking Market Index ARIMA_PLUS model...")
    try:
        client.get_model(f"{project_id}.val_ml.market_index_arima_{v}")
        print("  = Market Index ARIMA+ model already trained. Skipping.")
    except NotFound:
        print("  - Training Market Index ARIMA_PLUS model...")
        sql_arima = f"""
        CREATE OR REPLACE MODEL `{project_id}.val_ml.market_index_arima_{v}`
        OPTIONS (
          model_type = 'ARIMA_PLUS',
          time_series_timestamp_col = 'month',
          time_series_data_col = 'median_ppsf',
          time_series_id_col = 'submarket',
          data_frequency = 'MONTHLY'
        ) AS
        SELECT month, submarket, median_ppsf FROM `{project_id}.val_ml.ppsf_monthly`;
        """
        job = client.query(sql_arima)
        job.result()
        print("  + Market Index ARIMA+ model trained.")

    # Populate smoothed market index & forecast into val_core.market_index
    sql_populate_idx = f"""
    CREATE OR REPLACE TABLE `{project_id}.val_core.market_index` (
      submarket STRING, month DATE, median_ppsf FLOAT64, n_sales INT64, is_forecast BOOL, model_version STRING, built_at TIMESTAMP
    );

    INSERT INTO `{project_id}.val_core.market_index` (submarket, month, median_ppsf, n_sales, is_forecast, model_version, built_at)
    SELECT submarket, month,
           AVG(median_ppsf) OVER (PARTITION BY submarket ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW),
           n_sales, FALSE, '{v}', CURRENT_TIMESTAMP()
    FROM `{project_id}.val_ml.ppsf_monthly`;

    INSERT INTO `{project_id}.val_core.market_index` (submarket, month, median_ppsf, n_sales, is_forecast, model_version, built_at)
    SELECT submarket, DATE(forecast_timestamp), forecast_value, NULL, TRUE, '{v}', CURRENT_TIMESTAMP()
    FROM ML.FORECAST(MODEL `{project_id}.val_ml.market_index_arima_{v}`, STRUCT(6 AS horizon));
    """
    job = client.query(sql_populate_idx)
    job.result()
    print("  + val_core.market_index populated with actuals & 6-month forecast.")

    # 3. Time-adjusted sales view
    print("\n[3/6] Creating sales_time_adjusted view...")
    sql_time_adj = f"""
    CREATE OR REPLACE VIEW `{project_id}.val_ml.sales_time_adjusted` AS
    WITH idx AS (
      SELECT submarket, month, median_ppsf FROM `{project_id}.val_core.market_index` WHERE NOT is_forecast
    ),
    latest AS (
      SELECT submarket, ARRAY_AGG(median_ppsf ORDER BY month DESC LIMIT 1)[OFFSET(0)] AS ppsf_now
      FROM idx GROUP BY submarket
    )
    SELECT sf.*, l.ppsf_now / i.median_ppsf AS time_adj_factor,
           sf.price * l.ppsf_now / i.median_ppsf AS price_time_adj
    FROM `{project_id}.val_ml.sales_features` sf
    JOIN idx i ON i.submarket = sf.submarket AND i.month = sf.sale_month
    JOIN latest l ON l.submarket = sf.submarket;
    """
    job = client.query(sql_time_adj)
    job.result()
    print("  + sales_time_adjusted view created.")

    # 4. Comp ranker (BOOSTED_TREE_CLASSIFIER)
    print("\n[4/6] Checking Comp Ranker (BOOSTED_TREE_CLASSIFIER)...")
    try:
        client.get_model(f"{project_id}.val_ml.comp_ranker_{v}")
        print("  = Comp Ranker model already trained. Skipping.")
    except NotFound:
        print("  - Training Comp Ranker model...")
        sql_ranker = f"""
        CREATE OR REPLACE MODEL `{project_id}.val_ml.comp_ranker_{v}`
        OPTIONS (
          model_type = 'BOOSTED_TREE_CLASSIFIER',
          input_label_cols = ['accepted'],
          max_iterations = 30,
          enable_global_explain = TRUE
        ) AS
        SELECT dist_mi, months_since_sale, gla_diff_pct, beds_diff, baths_diff, age_diff_yrs,
               lot_diff_pct, condition_diff, quality_diff, same_submarket, pool_mismatch, accepted
        FROM `{project_id}.val_ops.comp_feedback`
        WHERE approved;
        """
        job = client.query(sql_ranker)
        job.result()
        print("  + Comp Ranker model trained.")

    # 5. Submarket Adjustment Grids (LINEAR_REG per submarket)
    print("\n[5/6] Training submarket adjustment grids (LINEAR_REG)...")
    submarkets = [("Larkspur", "larkspur"), ("Old Town", "old_town"), ("Hilltop", "hilltop"), ("Riverside", "riverside")]

    # Table for adjustment grid coefficients
    client.query(f"""
    DELETE FROM `{project_id}.val_ml.adjustment_grid` WHERE TRUE;
    """).result()

    for subm_name, slug in submarkets:
        print(f"  - Training adjustment grid for {subm_name}...")
        sql_subm = f"""
        CREATE OR REPLACE MODEL `{project_id}.val_ml.adj_{slug}_{v}`
        OPTIONS (
          model_type = 'LINEAR_REG',
          input_label_cols = ['price_time_adj'],
          l2_reg = 1.0,
          enable_global_explain = TRUE
        ) AS
        SELECT gla_sqft, beds, baths_total, age_yrs, lot_sqft, pool, garage_spaces,
               condition_c, quality_q, price_time_adj
        FROM `{project_id}.val_ml.sales_time_adjusted`
        WHERE submarket = '{subm_name}' AND sale_type = 'arms_length';

        INSERT INTO `{project_id}.val_ml.adjustment_grid` (submarket, feature, dollars_per_unit, clamped, model_name, built_at)
        SELECT '{subm_name}', processed_input AS feature, CAST(weight AS NUMERIC) AS dollars_per_unit, FALSE, 'adj_{slug}_{v}', CURRENT_TIMESTAMP()
        FROM ML.WEIGHTS(MODEL `{project_id}.val_ml.adj_{slug}_{v}`)
        WHERE processed_input != '__INTERCEPT__';
        """
        job = client.query(sql_subm)
        job.result()

    print("  + All 4 submarket adjustment grids trained and stored in val_ml.adjustment_grid.")

    # 6. AVM (BOOSTED_TREE_REGRESSOR)
    print("\n[6/6] Training AVM (BOOSTED_TREE_REGRESSOR) with time split...")
    sql_avm = f"""
    CREATE OR REPLACE MODEL `{project_id}.val_ml.avm_{v}`
    OPTIONS (
      model_type = 'BOOSTED_TREE_REGRESSOR',
      input_label_cols = ['price_time_adj'],
      data_split_method = 'CUSTOM',
      data_split_col = 'is_eval',
      max_iterations = 25,
      enable_global_explain = TRUE
    ) AS
    SELECT gla_sqft, beds, baths_total, age_yrs, lot_sqft, pool, garage_spaces,
           condition_c, quality_q, submarket, property_type, lat, lng,
           price_time_adj,
           sale_date >= DATE_SUB((SELECT MAX(sale_date) FROM `{project_id}.val_core.sales`), INTERVAL 4 MONTH) AS is_eval
    FROM `{project_id}.val_ml.sales_time_adjusted`;
    """
    job = client.query(sql_avm)
    job.result()
    print("  + AVM Boosted Tree Regressor trained.")

    print("\n=== All BQML Models Successfully Trained and Ready on BigQuery! ===")


if __name__ == "__main__":
    train_bqml_models()
