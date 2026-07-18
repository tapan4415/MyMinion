.PHONY: install dev api web ios test verify

install:
	python -m pip install -e './agent-py[dev]'
	npm install

api:
	uvicorn lifeops.api.app:app --app-dir agent-py/src --reload

web:
	npm run dev

ios:
	npm run dev:ios

test:
	pytest agent-py/tests

verify:
	python -m compileall -q agent-py/src
	pytest agent-py/tests
	npm run typecheck
	npm run build
