"""Tests for the AWS adapter."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastmcp import Client
from spine import Core

from conduit.adapters.aws import server as aws_server
from conduit.config import AwsConfig, Config
from conduit.gate import reset_counters
from tests.adapters.conftest import MockTokenStore


@pytest.fixture
def aws_core():
    config = Config(aws=AwsConfig(
        enabled=True,
        region="us-east-1",
        rate_limit=100,
        rate_window=1,
    ))
    tokens = MockTokenStore()

    def setup(c):
        c.register("config", config)
        c.register("tokens", tokens)
        c.boot(env="test")

    Core.boot_once(setup)
    reset_counters()
    return Core.instance()


# ---------------------------------------------------------------------------
# aws_list_buckets
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_aws_list_buckets(aws_core):
    mock_boto3 = MagicMock()
    mock_s3 = MagicMock()
    mock_boto3.client.return_value = mock_s3
    mock_s3.list_buckets.return_value = {
        "Buckets": [
            {"Name": "my-bucket", "CreationDate": datetime(2024, 1, 1, tzinfo=timezone.utc)},
            {"Name": "other-bucket", "CreationDate": datetime(2024, 6, 15, tzinfo=timezone.utc)},
        ]
    }

    with patch("conduit.adapters.aws.boto3", mock_boto3):
        async with Client(aws_server) as client:
            result = await client.call_tool("aws_list_buckets", {})

    result_str = str(result)
    assert "my-bucket" in result_str
    assert "other-bucket" in result_str
    mock_boto3.client.assert_called_once_with("s3", region_name="us-east-1")
    mock_s3.list_buckets.assert_called_once()


@pytest.mark.asyncio
async def test_aws_list_buckets_empty(aws_core):
    mock_boto3 = MagicMock()
    mock_s3 = MagicMock()
    mock_boto3.client.return_value = mock_s3
    mock_s3.list_buckets.return_value = {"Buckets": []}

    with patch("conduit.adapters.aws.boto3", mock_boto3):
        async with Client(aws_server) as client:
            result = await client.call_tool("aws_list_buckets", {})

    assert "[]" in str(result) or result == [] or "[]" in repr(result)


# ---------------------------------------------------------------------------
# aws_list_objects
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_aws_list_objects(aws_core):
    mock_boto3 = MagicMock()
    mock_s3 = MagicMock()
    mock_boto3.client.return_value = mock_s3
    mock_s3.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "data/file1.txt", "Size": 1024, "LastModified": datetime(2024, 3, 1, tzinfo=timezone.utc)},
            {"Key": "data/file2.csv", "Size": 4096, "LastModified": datetime(2024, 3, 2, tzinfo=timezone.utc)},
        ]
    }

    with patch("conduit.adapters.aws.boto3", mock_boto3):
        async with Client(aws_server) as client:
            result = await client.call_tool("aws_list_objects", {
                "bucket": "my-bucket",
                "prefix": "data/",
                "max_keys": 10,
            })

    result_str = str(result)
    assert "data/file1.txt" in result_str
    assert "data/file2.csv" in result_str
    assert "1024" in result_str
    assert "4096" in result_str
    mock_boto3.client.assert_called_once_with("s3", region_name="us-east-1")
    mock_s3.list_objects_v2.assert_called_once_with(
        Bucket="my-bucket", Prefix="data/", MaxKeys=10
    )


@pytest.mark.asyncio
async def test_aws_list_objects_empty_prefix(aws_core):
    """list_objects with default prefix returns all objects."""
    mock_boto3 = MagicMock()
    mock_s3 = MagicMock()
    mock_boto3.client.return_value = mock_s3
    mock_s3.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "readme.md", "Size": 256, "LastModified": datetime(2024, 1, 10, tzinfo=timezone.utc)},
        ]
    }

    with patch("conduit.adapters.aws.boto3", mock_boto3):
        async with Client(aws_server) as client:
            result = await client.call_tool("aws_list_objects", {"bucket": "my-bucket"})

    result_str = str(result)
    assert "readme.md" in result_str
    assert "256" in result_str
    # Verify count is included
    assert "1" in result_str


# ---------------------------------------------------------------------------
# aws_describe_instances
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_aws_describe_instances(aws_core):
    mock_boto3 = MagicMock()
    mock_ec2 = MagicMock()
    mock_boto3.client.return_value = mock_ec2
    mock_ec2.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0abc123",
                        "InstanceType": "t3.micro",
                        "State": {"Name": "running"},
                        "PublicIpAddress": "54.1.2.3",
                        "PrivateIpAddress": "10.0.0.5",
                        "Tags": [{"Key": "Name", "Value": "web-server"}],
                    }
                ]
            }
        ]
    }

    with patch("conduit.adapters.aws.boto3", mock_boto3):
        async with Client(aws_server) as client:
            result = await client.call_tool("aws_describe_instances", {"instance_ids": ["i-0abc123"]})

    result_str = str(result)
    assert "i-0abc123" in result_str
    assert "web-server" in result_str
    assert "t3.micro" in result_str
    assert "running" in result_str
    assert "54.1.2.3" in result_str
    mock_boto3.client.assert_called_once_with("ec2", region_name="us-east-1")
    mock_ec2.describe_instances.assert_called_once_with(InstanceIds=["i-0abc123"])


@pytest.mark.asyncio
async def test_aws_describe_instances_all(aws_core):
    """Empty instance_ids should call describe_instances with no InstanceIds kwarg."""
    mock_boto3 = MagicMock()
    mock_ec2 = MagicMock()
    mock_boto3.client.return_value = mock_ec2
    mock_ec2.describe_instances.return_value = {"Reservations": []}

    with patch("conduit.adapters.aws.boto3", mock_boto3):
        async with Client(aws_server) as client:
            result = await client.call_tool("aws_describe_instances", {})

    # Should be called without InstanceIds
    mock_ec2.describe_instances.assert_called_once_with()


# ---------------------------------------------------------------------------
# aws_cloudwatch_metrics
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_aws_cloudwatch_metrics(aws_core):
    mock_boto3 = MagicMock()
    mock_cw = MagicMock()
    mock_boto3.client.return_value = mock_cw
    mock_cw.list_metrics.return_value = {
        "Metrics": [
            {"Namespace": "AWS/EC2", "MetricName": "CPUUtilization", "Dimensions": [{"Name": "InstanceId", "Value": "i-0abc"}]},
            {"Namespace": "AWS/EC2", "MetricName": "CPUUtilization", "Dimensions": [{"Name": "InstanceId", "Value": "i-0def"}]},
            {"Namespace": "AWS/EC2", "MetricName": "NetworkIn", "Dimensions": []},
        ]
    }

    with patch("conduit.adapters.aws.boto3", mock_boto3):
        async with Client(aws_server) as client:
            result = await client.call_tool("aws_cloudwatch_metrics", {"namespace": "AWS/EC2"})

    result_str = str(result)
    assert "CPUUtilization" in result_str
    assert "NetworkIn" in result_str
    # CPUUtilization should appear only once (deduplicated) — check the JSON payload
    import json
    text_content = result.content[0].text
    parsed = json.loads(text_content)
    names = [m["name"] for m in parsed]
    assert names.count("CPUUtilization") == 1
    assert len(parsed) == 2
    mock_boto3.client.assert_called_once_with("cloudwatch", region_name="us-east-1")
    mock_cw.list_metrics.assert_called_once_with(Namespace="AWS/EC2")
