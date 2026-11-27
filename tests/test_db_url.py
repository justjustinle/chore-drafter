from app.db import normalise_url


def test_hosted_urls_get_the_psycopg_driver():
    assert normalise_url("postgres://u:p@host/db?sslmode=require") == "postgresql+psycopg://u:p@host/db?sslmode=require"
    assert normalise_url("postgresql://u:p@host/db") == "postgresql+psycopg://u:p@host/db"


def test_urls_that_already_name_a_driver_are_left_alone():
    url = "postgresql+psycopg://chore:chore@localhost:5432/chore_draft"
    assert normalise_url(url) == url
