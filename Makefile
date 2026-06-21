.PHONY: orchestrator study calendar workload wellness smoke-test demo

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
