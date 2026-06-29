"""CLI smoke tests (argparse wiring + the --calibrate flag)."""
from realpath import cli


def test_schema_command(sample_db, capsys):
    cli.main(["schema", "--db", sample_db])
    out = capsys.readouterr().out
    assert "customers" in out
    assert "Foreign keys" in out


def test_predict_with_calibrate(sample_db, capsys):
    cli.main([
        "predict",
        "PREDICT COUNT(transactions.*, 0, 30, days) == 0 FOR EACH customers.customer_id",
        "--db", sample_db, "--calibrate", "--top", "3",
    ])
    out = capsys.readouterr().out
    assert "metrics:" in out and "roc_auc" in out
    assert "calibration:" in out           # Brier/ECE printed only with --calibrate
    assert "brier" in out and "ece" in out
    assert "top predictions:" in out
