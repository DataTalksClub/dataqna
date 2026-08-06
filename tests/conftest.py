import os

import boto3
import pytest
from moto import mock_aws

os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("TABLE_NAME", "dataqna-test")
os.environ.setdefault("SITE_URL", "https://qna.test")
os.environ.setdefault("ROOT_ADMIN", "root@datatalks.club")
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-1")


@pytest.fixture
def table():
    with mock_aws():
        client = boto3.resource("dynamodb", region_name="eu-west-1")
        client.create_table(
            TableName="dataqna-test",
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "GSI1PK", "AttributeType": "S"},
                {"AttributeName": "GSI1SK", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "GSI1",
                    "KeySchema": [
                        {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
        )
        from dataqna import store

        store._table = None
        yield client.Table("dataqna-test")
        store._table = None
