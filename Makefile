.PHONY: build deploy validate test verify

build:
	sam build --config-env sandbox

deploy:
	sam deploy --config-env sandbox

validate:
	sam validate --lint

test:
	uv run --with boto3 --with moto --with pytest --with pyjwt --with segno env \
		PYTHONPATH=src SESSION_SECRET=test-secret AWS_ACCESS_KEY_ID=testing \
		AWS_SECRET_ACCESS_KEY=testing AWS_DEFAULT_REGION=eu-west-1 pytest -q

verify:
	uv run --with requests python scripts/verify_deployment.py
