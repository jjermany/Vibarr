from pathlib import Path


ENTRYPOINT = Path(__file__).resolve().parents[2] / "entrypoint.sh"


def test_entrypoint_makes_config_directory_traversable_for_postgres():
    script = ENTRYPOINT.read_text()

    assert "chmod 755 /config" in script


def test_entrypoint_recursively_fixes_postgres_data_ownership_and_perms():
    script = ENTRYPOINT.read_text()

    assert 'chown -R postgres:postgres "$PG_DATA"' in script
    assert 'chmod 700 "$PG_DATA"' in script
    assert '[ -f "$PG_DATA/postgresql.conf" ] && chmod 600 "$PG_DATA/postgresql.conf"' in script
    assert '[ -f "$PG_DATA/pg_hba.conf" ] && chmod 600 "$PG_DATA/pg_hba.conf"' in script
