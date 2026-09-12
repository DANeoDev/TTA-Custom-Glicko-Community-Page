# Command-Line Interface (CLI) Reference

This guide covers the CLI tools available in the repository.

---

## 1. Master Pipeline (`run_pipeline.py`)

The primary tool for data ingestion and full rating recalculation across all models.

### Basic Usage
```bash
# Ingest raw CSV files and calculate all 3 rating models:
python run_pipeline.py
```

### Options
- `--skip-ingest`: Skips re-reading `all_matches.csv` and `ratings_overall.csv`. Useful when you only want to re-run the rating calculations using the existing SQLite database.
```bash
python run_pipeline.py --skip-ingest
```

---

## 2. Web Portal Server (`run_web.py`)

Launches the standalone Flask server with all interactive views.

### Basic Usage
```bash
python run_web.py
```

### Configuration Environment Variables
- `PORT`: HTTP port to bind to (Default: `5050`).
- `TTA_SECRET_KEY`: Flask session secret key.

```bash
PORT=8080 python run_web.py
```

---

## 3. Running Automated Tests

Run the full test suite using `pytest`:
```bash
# Run all tests with verbose output:
pytest tests -v

# Run specific test modules:
pytest tests/test_glicko2.py -v
pytest tests/test_pairwise.py -v
pytest tests/test_whr.py -v
pytest tests/test_web.py -v
```
