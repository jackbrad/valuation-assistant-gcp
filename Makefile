.PHONY: setup infra data pipeline models app deploy demo-reset test test-gcp breaker clean

VENV := .venv
PYTHON := uv run python
PYTEST := uv run pytest

setup:
	uv sync

infra:
	@echo "Checking GCP credentials..."
	$(PYTHON) scripts/check_gcp.py
	@echo "Applying infrastructure..."
	$(PYTHON) scripts/setup_infra.py

data:
	@echo "Generating synthetic dataset..."
	$(PYTHON) -m data_gen.generator --seed 20261005
	@echo "Uploading dataset to GCS and BigQuery..."
	$(PYTHON) scripts/seed.py

pipeline:
	@echo "Running ingestion, parsing, entity resolution, and G1 data gate..."
	$(PYTHON) -m pipeline.run_pipeline

models:
	@echo "Training BQML models..."
	$(PYTHON) scripts/train_models.py

app:
	@echo "Starting FastAPI app locally on http://localhost:8000..."
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

deploy:
	@echo "Deploying valuation-app to Cloud Run..."
	$(PYTHON) scripts/deploy.py

demo-reset:
	@echo "Resetting demo state to baseline..."
	$(PYTHON) scripts/demo_reset.py

breaker:
	@echo "Running circuit breaker drift detection..."
	$(PYTHON) -m jobs.breaker

test:
	@echo "Running local unit tests..."
	$(PYTEST) -m "not gcp"

test-gcp:
	@echo "Running full integration test suite against GCP..."
	$(PYTEST)

clean:
	rm -rf data_gen/out/
	find . -type d -name "__pycache__" -exec rm -rf {} +
