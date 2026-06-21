.PHONY: orchestrator study calendar wellness smoke-test demo

orchestrator:
	.venv/bin/python agent.py

study:
	.venv/bin/python study_agent.py

calendar:
	.venv/bin/python calendar_agent.py

wellness:
	.venv/bin/python wellness_agent.py

smoke-test:
	.venv/bin/python smoke_test_agent.py

demo:
	.venv/bin/python main.py
