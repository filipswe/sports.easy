from app.models import Quote
from app.research import all_rows
from sqlalchemy import event, select


def test_match_listing_uses_bounded_queries_and_small_selector_payload(client, db):
    statements = []

    def count(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db.bind, "before_cursor_execute", count)
    try:
        response = client.get("/api/matchday?period=fortnight&summary=true")
        assert response.status_code == 200
        rows = response.json()["items"]
        assert len(rows) == 60
        assert all(row["markets"] == [] and row["prediction_id"] for row in rows)
        assert len(response.content) < 60_000
        assert len(statements) <= 14
        statements.clear()
        response = client.get("/api/matchday?market=1x2")
        assert response.status_code == 200
        rows = response.json()["items"]
        assert all([market["key"] for market in row["markets"]] == ["1x2"] for row in rows)
        assert len(statements) <= 14
        # Full detail remains available, including unpriced model markets.
        detail = client.get("/api/matchday/" + rows[0]["id"]).json()
        assert any(market["key"] == "half_totals_0.5" for market in detail["markets"])
    finally:
        event.remove(db.bind, "before_cursor_execute", count)


def test_publication_rows_load_teams_and_competition_in_one_query(db):
    statements = []

    def count(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    core_ids = list(db.scalars(select(Quote.id).where(Quote.market.in_(["1x2", "totals", "btts"]))))
    event.listen(db.bind, "before_cursor_execute", count)
    try:
        rows = all_rows(db, quote_ids=core_ids)
        assert len(rows) == 840
        assert len(statements) == 1
        assert all(row["home"] and row["away"] and row["competition"] for row in rows)
    finally:
        event.remove(db.bind, "before_cursor_execute", count)
