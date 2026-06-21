.PHONY: app orchestrator study calendar workload wellness smoke-test demo

app:
	./start-busy-brain.sh

orchestrator:
	.venv/bin/python agent.py

study:
	.venv/bin/python study_agent.py

calendar:
	.venv/bin/python calendar_agent.py

workload:
	.venv/bin/python wellness_agent.py

wellness: workload

smoke-test:
	.venv/bin/python smoke_test_agent.py

demo:
	.venv/bin/python main.py
