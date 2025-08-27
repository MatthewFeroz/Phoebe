from fastapi import FastAPI, HTTPException
from app.database import shifts_db, caregivers_db, load_sample_data
from app.notifier import send_sms, place_phone_call
import logging

import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    app = FastAPI()
    
    load_sample_data()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # This line tells FastAPI to handle HTTP POST requests sent to the URL path "/shifts/{shift_id}/fanout" with the function defined below it.
    @app.post("/shifts/{shift_id}/fanout")
    async def fanout_shift(shift_id: str):
        shift = shifts_db.get(shift_id)
        if not shift:
            raise HTTPException(status_code=404, detail="Shift not found")

        # If the shift has already been claimed, do nothing and return the current state (this makes the operation safe to repeat without side effects)
        if shift["status"] == "claimed":
            return {"message": "Shift already claimed", "shift": shift}

        # If already fanned out → idempotent no-op
        if shift["fanout_round"] >= 1:
            return {"message": "Fanout already triggered", "shift": shift}

        # Round 1: SMS fanout
        eligible_caregivers = [
            # Iterate over all caregivers in the caregivers_db.
            c for c in caregivers_db.all()
            if c["role"] == shift["role_required"]
        ]

        # Iterate over all eligible caregivers and send an SMS to each one.
        for caregiver in eligible_caregivers:
            await send_sms(
                caregiver["phone"],
                f"Shift available: {shift['id']}"
            )
            # Add the caregiver's ID to the list of contacted caregivers.
            shift["contacted"].append(caregiver["id"])

        # Update the shift's fanout round to 1.
        shift["fanout_round"] = 1
        shifts_db.put(shift_id, shift)

        # Schedule escalation after 10 minutes
        asyncio.create_task(escalate_to_phone(shift_id))

        return {"message": "Fanout started", "shift": shift}

    return app


async def escalate_to_phone(shift_id: str):
    await asyncio.sleep(30)  # 30 seconds
    shift = shifts_db.get(shift_id)
    if shift and shift["status"] == "open" and shift["fanout_round"] == 1:
        eligible_caregivers = [
            c for c in caregivers_db.all()
            if c["role"] == shift["role_required"]
        ]
        for caregiver in eligible_caregivers:
            await place_phone_call(
                caregiver["phone"],
                f"Shift available: {shift['id']}"
            )
            shift["contacted"].append(caregiver["id"])
        shift["fanout_round"] = 2
        shifts_db.put(shift_id, shift)