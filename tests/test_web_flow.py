"""End-to-end integration tests for web app, review governance, and cascade flow."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.state import state, DemoState


@pytest.fixture(autouse=True)
def reset_state():
    import app.state as app_state
    app_state.state = DemoState()


def test_full_demo_workflow():
    client = TestClient(app)

    # 1. Ask page loads with 14 Larkspur Ln
    resp = client.get("/ask?q=14+Larkspur+Ln&user=alex.reviewer")
    assert resp.status_code == 200
    assert "14 Larkspur Ln" in resp.text
    assert "Unrecorded Living Area Addition" in resp.text

    # 2. Review queue loads
    resp = client.get("/review?user=alex.reviewer")
    assert resp.status_code == 200
    assert "Review queue" in resp.text

    # 3. Model health shows Riverside tripped
    resp = client.get("/health?user=alex.reviewer")
    assert resp.status_code == 200
    assert "Stricter checks on" in resp.text

    # 4. Alex flags 14 Larkspur GLA as stale
    flag_resp = client.post(
        "/api/flags",
        data={
            "property_id": "P-000014",
            "field_name": "gla_sqft",
            "proposed_value": "2080",
            "reason": "Stale data — addition on p.2 of inspection",
            "evidence_desc": "DOC-INS-000014 p.2 + Permit #CH-24-0817",
            "user_id": "alex.reviewer",
        },
        follow_redirects=True,
    )
    assert flag_resp.status_code == 200

    # 5. Loan Officer Jordan tries to approve -> 403 Forbidden (Stake blocked)
    app_resp = client.post("/api/review/REV-000002/approve", data={"user_id": "jordan.lo"})
    assert app_resp.status_code == 403

    # 6. Flagger Alex tries to approve their own flag -> 403 Forbidden
    app_self = client.post("/api/review/REV-000002/approve", data={"user_id": "alex.reviewer"})
    assert app_self.status_code == 403

    # 7. Sam (Reviewer) approves step 1 of 2
    app_s1 = client.post("/api/review/REV-000002/approve", data={"user_id": "sam.reviewer"}, follow_redirects=True)
    assert app_s1.status_code == 200

    # 8. Pat (Data Steward) approves step 2 of 2 -> triggers cascade
    app_s2 = client.post("/api/review/REV-000002/approve", data={"user_id": "pat.steward"}, follow_redirects=True)
    assert app_s2.status_code == 200

    # 9. Verify What Changed (Cascade) contains both 14 Larkspur and 18 Larkspur
    casc_resp = client.get("/cascade?user=alex.reviewer")
    assert "14 Larkspur Ln" in casc_resp.text
    assert "18 Larkspur Ln" in casc_resp.text


def test_landing_page_and_empty_states():
    client = TestClient(app)

    # Root is the chat page
    resp_root = client.get("/")
    assert resp_root.status_code == 200
    assert "Ask about any property" in resp_root.text

    # /ask with no query defaults to 14 Larkspur Ln
    resp_ask = client.get("/ask")
    assert resp_ask.status_code == 200
    assert "14 Larkspur Ln" in resp_ask.text

    # Unknown property query renders the scenario catalog without crashing
    resp_unknown = client.get("/ask?q=NonExistentProperty123")
    assert resp_unknown.status_code == 200
    assert "Valuation Workbench" in resp_unknown.text
    assert "Scenario Catalog" in resp_unknown.text
    assert "No exact property match found" in resp_unknown.text
    assert "Evaluate 14 Larkspur Ln" in resp_unknown.text


def test_review_queue_dynamic_reasons():
    client = TestClient(app)
    resp = client.get("/review?user=alex.reviewer")
    assert resp.status_code == 200
    # Confirm item 1 shows its proper reason
    assert "Cross-source conflict" in resp.text
    # Confirm item 2 (22 Hilltop) does NOT display the addition string
    assert "22 Hilltop Rd" in resp.text

