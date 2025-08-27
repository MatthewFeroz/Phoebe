from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
import asyncio
from freezegun import freeze_time
from httpx import ASGITransport, AsyncClient
from app.api import create_app, escalate_to_phone
from app.database import load_sample_data, shifts_db, caregivers_db
import app.api

app.api.ESCALATION_DELAY = 0.1  # fast-forward for tests

@pytest_asyncio.fixture
async def client():
    """
    Test fixture that creates an async client for the API.
    """
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """
    Example test that uses the api client fixture to test the health check
    endpoint.
    """
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_mocked_time(client: AsyncClient) -> None:
    """
    Example test that shows how to mock time, including freezing time at a
    deterministic point and manually ticking time forward.
    """
    with freeze_time("2025-07-02 00:00:00") as frozen_time:
        assert datetime.now(UTC) == datetime(2025, 7, 2, 0, 0, 0, tzinfo=UTC)

        frozen_time.tick(delta=timedelta(seconds=60))

        assert datetime.now(UTC) == datetime(2025, 7, 2, 0, 1, 0, tzinfo=UTC)

@pytest.mark.asyncio
async def test_caregiver_can_claim_shift(client: AsyncClient):
    # Reset DB before test
    shifts_db.clear()
    load_sample_data()

    shift_id = "f5a9d844-ecff-4f7a-8ef7-d091f22ad77e"  # RN shift
    caregiver_phone = "+15550001"  # Alice Ongwele, RN

    response = await client.post(
        "/messages/inbound",
        json={
            "from_number": caregiver_phone,
            "shift_id": shift_id,
            "body": "Yes, I accept"
        },
    )

    data = response.json()

    # Assertions
    assert response.status_code == 200
    assert data["message"] == "Shift successfully claimed"
    assert data["shift"]["status"] == "claimed"
    assert data["shift"]["assigned_caregiver"] is not None

@pytest.mark.asyncio
async def test_only_eligible_caregivers_contacted(client: AsyncClient):
    shifts_db.clear()
    load_sample_data()
    shift_id = "f5a9d844-ecff-4f7a-8ef7-d091f22ad77e"  # RN shift

    await client.post(f"/shifts/{shift_id}/fanout")
    shift = shifts_db.get(shift_id)

    # All contacted caregivers must be RNs
    for cid in shift["contacted"]:
        caregiver = caregivers_db.get(cid)
        assert caregiver["role"] == "RN"

@pytest.mark.asyncio
async def test_decline_message(client: AsyncClient):
    shifts_db.clear()
    load_sample_data()
    shift_id = "f5a9d844-ecff-4f7a-8ef7-d091f22ad77e"

    response = await client.post(
        "/messages/inbound",
        json={"from_number": "+15550001", "shift_id": shift_id, "body": "No, I cannot"},
    )
    data = response.json()
    assert data["message"] == "Caregiver declined the shift"

# This test is not required unless you want to speed up escalation for tests.
@pytest.mark.asyncio
async def test_escalation_to_phone(client: AsyncClient):
    shifts_db.clear()
    load_sample_data()
    shift_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

    # Trigger fanout (SMS round)
    await client.post(f"/shifts/{shift_id}/fanout")
    shift = shifts_db.get(shift_id)
    assert shift["fanout_round"] == 1

    # Call escalation directly
    await escalate_to_phone(shift_id)

    shift = shifts_db.get(shift_id)
    assert shift["fanout_round"] == 2

@pytest.mark.asyncio
async def test_second_caregiver_cannot_claim(client: AsyncClient):
    shifts_db.clear()
    load_sample_data()
    shift_id = "f5a9d844-ecff-4f7a-8ef7-d091f22ad77e"

    # First caregiver claims
    await client.post(
        "/messages/inbound",
        json={"from_number": "+15550001", "shift_id": shift_id, "body": "Yes, I accept"},
    )

    # Second caregiver tries
    response = await client.post(
        "/messages/inbound",
        json={"from_number": "+15550002", "shift_id": shift_id, "body": "Yes, I accept"},
    )
    data = response.json()
    assert data["message"] == "Shift already claimed"

@pytest.mark.asyncio
async def test_fanout_is_idempotent(client: AsyncClient):
    shifts_db.clear()
    load_sample_data()
    shift_id = "f5a9d844-ecff-4f7a-8ef7-d091f22ad77e"  # RN shift

    # First fanout
    await client.post(f"/shifts/{shift_id}/fanout")
    shift = shifts_db.get(shift_id)
    first_contacted = set(shift["contacted"])
    assert len(first_contacted) > 0  # caregivers were contacted

    # Second fanout (should not duplicate)
    await client.post(f"/shifts/{shift_id}/fanout")
    shift = shifts_db.get(shift_id)
    second_contacted = set(shift["contacted"])

    # Assert no new caregivers were added
    assert first_contacted == second_contacted
    assert shift["fanout_round"] == 1  # still SMS round, not duplicated


@pytest.mark.asyncio
async def test_inbound_is_idempotent(client: AsyncClient):
    shifts_db.clear()
    load_sample_data()
    shift_id = "f5a9d844-ecff-4f7a-8ef7-d091f22ad77e"
    caregiver_phone = "+15550001"  # Alice Ongwele, RN

    # First accept
    response1 = await client.post(
        "/messages/inbound",
        json={"from_number": caregiver_phone, "shift_id": shift_id, "body": "Yes, I accept"},
    )
    data1 = response1.json()
    assert data1["message"] == "Shift successfully claimed"
    assigned = data1["shift"]["assigned_caregiver"]

    # Second accept (same caregiver, same shift)
    response2 = await client.post(
        "/messages/inbound",
        json={"from_number": caregiver_phone, "shift_id": shift_id, "body": "Yes, I accept"},
    )
    data2 = response2.json()

    # Assert shift is still assigned to the same caregiver, no duplication
    assert data2["shift"]["assigned_caregiver"] == assigned
    assert data2["shift"]["status"] == "claimed"