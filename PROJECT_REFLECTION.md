See [README.md](README.md) for instructions.
Upon completion, write a brief reflection on the project in [PROJECT_REFLECTION.md](PROJECT_REFLECTION.md). Include:

- Explanation of any design decisions or tradeoffs made.
- Explanation of how you used LLM tools in your process (if applicable).

Summary:
I built this service with an in-memory database for simplicity, adding fields to shifts to track 
state and enforce first-come-first-serve. Escalation was implemented as a background task and I added simple idempotency
checks to avoid duplicate fanouts or claims. Tests were written to directly validate all functional requirements. 
GPT-5 helped me plan the architecture, design schemas, and map tests to requirements, while I 
focused on debugging async behavior and ensuring correctness.


Design Decisions/Tradeoffs: 

1) In-Memory DB
I implemented a InMemoryKeyValueDatabase class to store the caregivers and shifts with two global stores caregivers_db and shifts_db.
This fufilled the requirement for avoiding persistent databases and allowed me to restart faster and easily.
The tradeoff I would say was you lose data on every restart, which wouldn't work in prod.

2) Updated Shift State Management
I added fields such as status, assigned_caregiver, fanout_round and if contacted to shift records.
This allowed me to track the progress of the fanout search, prevent notifications from duplciation and enforce the first come first serve requirement.
The tradeoff of this decision would be that the data model and business information are combining with eachother when they could be seperated for clarity.

3) Concurrency
I used asyncio.Lock to prevent race conditions when multiple caregivers try to claim the same shift
This ensures only one caregiver can win the shift, even under concurrent requests
This only works within a single process, in a distrubted system I would need to have a transactional database

4) Escalation Logic
I implemented escalation as a background task that sleeps for 10 mins before sending phone notifications
This matched the requirement for a two-round escalation (SMS -> phone) without introducing extrnal schedulers
The tradeoff is that background tests dont work all too well. 

5)Idempotency
I added checks so that repeated calls to /messages/inbound and /shifts/{id}/fanout do not duplicate notifications or reassign shifts
This ensures that the service is safe to retry
The tradeoff is that the idempotency logic is pretty simple, I would need better guarantees like requests IDs to ensure idempotency

6)Testing
I created 7 tests that directly map to the functional requirements of the project, health check, role filtering, escalation, first come first serve,
duplicate claim prevention, decline handling and idempotency.
This ensured that the MVP was validated
Some of the tests bypass background scheduling to avoid timing issues, this makes the testing a little less realistic than required for an actual app

How I used LLM Tools:

After reading through the entirety of the project requirements, I first mapped out a project roadmap to ensure that I spent my time on the highest
leverage portion of the project. I prompted GPT-5 using T3Chat to help me confirm that I would go from fanout → inbound → claim → escalation to ensure that I was convering spec.

I started with database.py, and was provided example schemas to quickly design how the caregivers and shifts db would work.

I then used AI to help me figure how to put shift locks in, ensuring that the service was concurrency safe.

I then used AI to help plan the skelton of the fanout endpoint, this part I used AI more because I wanted to ensure that the idemptoency checks worked properly
I had to fix some bugs myself here due to esclation tasks not running within the unit tests

I then had some errors with naming schemas and the way they were being referenced at the endpoint, the AI helped me catch these

For the testing I used the LLM to help me come up with specific tests to map the requirements of the projects to, but some had to be changed because they were calling the wrong things