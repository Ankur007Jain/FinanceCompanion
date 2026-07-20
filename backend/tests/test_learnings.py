"""Tests for /learnings endpoints — the settings-page CRUD surface for reviewing,
editing, and deleting saved learnings outside of chat."""
import uuid
from unittest.mock import patch

from models import UserLearning


def _email():
    return f"learn-{uuid.uuid4().hex[:8]}@example.com"


def _mock_user(email):
    return patch(
        "routers.auth.id_token.verify_oauth2_token",
        return_value={"email": email, "name": "Test"},
    )


class TestCreateLearning:
    def test_creates_global_note(self, client, db_session):
        e = _email()
        with _mock_user(e):
            r = client.post("/learnings", params={"id_token": "tok"}, json={"learning": "Prefers value stocks."})
        assert r.status_code == 200
        body = r.json()
        assert body["learning"] == "Prefers value stocks."
        assert body["ticker"] is None
        assert body["source"] == "user"
        db_session.expire_all()
        row = db_session.get(UserLearning, body["id"])
        assert row.source_conversation_id is None

    def test_creates_ticker_scoped_note(self, client):
        e = _email()
        with _mock_user(e):
            r = client.post("/learnings", params={"id_token": "tok"}, json={"learning": "Key supplier is XYZ.", "ticker": "abc"})
        assert r.status_code == 200
        assert r.json()["ticker"] == "ABC"

    def test_rejects_empty_text(self, client):
        e = _email()
        with _mock_user(e):
            r = client.post("/learnings", params={"id_token": "tok"}, json={"learning": "   "})
        assert r.status_code == 422

    def test_chat_saved_learning_has_chat_source(self, client, db_session):
        e = _email()
        db_session.add(UserLearning(user_email=e, learning="From chat.", source_conversation_id="conv-1"))
        db_session.commit()
        with _mock_user(e):
            r = client.get("/learnings", params={"id_token": "tok"})
        assert r.json()[0]["source"] == "chat"


class TestListLearnings:
    def test_empty_when_none_saved(self, client):
        e = _email()
        with _mock_user(e):
            r = client.get("/learnings", params={"id_token": "tok"})
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_both_global_and_ticker_scoped(self, client, db_session):
        e = _email()
        db_session.add(UserLearning(user_email=e, learning="Manages 48 stocks total."))
        db_session.add(UserLearning(user_email=e, ticker="SLV", learning="Already knows SLV/GLD overlap."))
        db_session.commit()
        with _mock_user(e):
            r = client.get("/learnings", params={"id_token": "tok"})
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 2
        tickers = {row["ticker"] for row in rows}
        assert tickers == {None, "SLV"}

    def test_only_returns_own_learnings(self, client, db_session):
        e1, e2 = _email(), _email()
        db_session.add(UserLearning(user_email=e1, learning="Belongs to user 1."))
        db_session.commit()
        with _mock_user(e2):
            r = client.get("/learnings", params={"id_token": "tok"})
        assert r.json() == []


class TestUpdateLearning:
    def test_edits_the_text(self, client, db_session):
        e = _email()
        row = UserLearning(user_email=e, learning="Original text.")
        db_session.add(row)
        db_session.commit()
        with _mock_user(e):
            r = client.patch(f"/learnings/{row.id}", params={"id_token": "tok"}, json={"learning": "Corrected text."})
        assert r.status_code == 200
        assert r.json()["learning"] == "Corrected text."
        db_session.expire_all()
        assert db_session.get(UserLearning, row.id).learning == "Corrected text."

    def test_rejects_empty_text(self, client, db_session):
        e = _email()
        row = UserLearning(user_email=e, learning="Keep me.")
        db_session.add(row)
        db_session.commit()
        with _mock_user(e):
            r = client.patch(f"/learnings/{row.id}", params={"id_token": "tok"}, json={"learning": "   "})
        assert r.status_code == 422
        db_session.expire_all()
        assert db_session.get(UserLearning, row.id).learning == "Keep me."

    def test_cannot_edit_another_users_learning(self, client, db_session):
        e1, e2 = _email(), _email()
        row = UserLearning(user_email=e1, learning="Not yours.")
        db_session.add(row)
        db_session.commit()
        with _mock_user(e2):
            r = client.patch(f"/learnings/{row.id}", params={"id_token": "tok"}, json={"learning": "Hijacked."})
        assert r.status_code == 404
        db_session.expire_all()
        assert db_session.get(UserLearning, row.id).learning == "Not yours."

    def test_unknown_id_returns_404(self, client):
        e = _email()
        with _mock_user(e):
            r = client.patch("/learnings/does-not-exist", params={"id_token": "tok"}, json={"learning": "X"})
        assert r.status_code == 404


class TestDeleteLearning:
    def test_deletes_own_learning(self, client, db_session):
        e = _email()
        row = UserLearning(user_email=e, learning="Delete me.")
        db_session.add(row)
        db_session.commit()
        row_id = row.id
        with _mock_user(e):
            r = client.delete(f"/learnings/{row_id}", params={"id_token": "tok"})
        assert r.status_code == 200
        db_session.expire_all()
        # A fresh query, not db.get() on the already-identity-mapped `row` object —
        # get() tries to refresh its now-stale attributes and raises ObjectDeletedError
        # instead of returning None; a new query against the DB just finds nothing.
        assert db_session.query(UserLearning).filter(UserLearning.id == row_id).first() is None

    def test_cannot_delete_another_users_learning(self, client, db_session):
        e1, e2 = _email(), _email()
        row = UserLearning(user_email=e1, learning="Not yours to delete.")
        db_session.add(row)
        db_session.commit()
        with _mock_user(e2):
            r = client.delete(f"/learnings/{row.id}", params={"id_token": "tok"})
        assert r.status_code == 404
        db_session.expire_all()
        assert db_session.get(UserLearning, row.id) is not None
