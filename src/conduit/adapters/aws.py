"""AWS adapter — 4 tools for S3, EC2, and CloudWatch."""
from __future__ import annotations

from typing import Annotated

import boto3
from fastmcp import FastMCP
from pydantic import Field
from spine import Core

from conduit.gate import check_gate

SERVICE = "aws"

server = FastMCP("AWS")


def _region() -> str:
    return Core.instance().get("config").aws.region


@server.tool
async def aws_list_buckets() -> list[dict]:
    """List all S3 buckets in the AWS account."""
    check_gate(SERVICE)
    s3 = boto3.client("s3", region_name=_region())
    response = s3.list_buckets()
    return [
        {
            "name": b["Name"],
            "created": b["CreationDate"].isoformat() if hasattr(b["CreationDate"], "isoformat") else str(b["CreationDate"]),
        }
        for b in response.get("Buckets", [])
    ]


@server.tool
async def aws_list_objects(
    bucket: Annotated[str, Field(description="S3 bucket name")],
    prefix: Annotated[str, Field(description="Key prefix to filter objects")] = "",
    max_keys: Annotated[int, Field(description="Maximum number of objects to return", ge=1, le=1000)] = 20,
) -> dict:
    """List objects in an S3 bucket, optionally filtered by prefix."""
    check_gate(SERVICE)
    s3 = boto3.client("s3", region_name=_region())
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=max_keys)
    objects = [
        {
            "key": obj["Key"],
            "size": obj["Size"],
            "modified": obj["LastModified"].isoformat() if hasattr(obj["LastModified"], "isoformat") else str(obj["LastModified"]),
        }
        for obj in response.get("Contents", [])
    ]
    return {
        "count": len(objects),
        "objects": objects,
    }


@server.tool
async def aws_describe_instances(
    instance_ids: Annotated[list[str], Field(description="List of EC2 instance IDs to describe; empty list returns all instances")] = [],
) -> list[dict]:
    """Describe EC2 instances, returning id, name, type, state, and IPs."""
    check_gate(SERVICE)
    ec2 = boto3.client("ec2", region_name=_region())
    kwargs = {}
    if instance_ids:
        kwargs["InstanceIds"] = instance_ids
    response = ec2.describe_instances(**kwargs)

    instances = []
    for reservation in response.get("Reservations", []):
        for inst in reservation.get("Instances", []):
            name = ""
            for tag in inst.get("Tags", []):
                if tag.get("Key") == "Name":
                    name = tag.get("Value", "")
                    break
            instances.append({
                "id": inst.get("InstanceId", ""),
                "name": name,
                "type": inst.get("InstanceType", ""),
                "state": inst.get("State", {}).get("Name", ""),
                "public_ip": inst.get("PublicIpAddress", ""),
                "private_ip": inst.get("PrivateIpAddress", ""),
            })
    return instances


@server.tool
async def aws_cloudwatch_metrics(
    namespace: Annotated[str, Field(description="CloudWatch namespace to list metrics for (e.g. 'AWS/EC2', 'AWS/S3')")],
) -> list[dict]:
    """List CloudWatch metrics for a given namespace, deduplicated by namespace+name."""
    check_gate(SERVICE)
    cw = boto3.client("cloudwatch", region_name=_region())
    response = cw.list_metrics(Namespace=namespace)

    seen: set[tuple[str, str]] = set()
    metrics = []
    for m in response.get("Metrics", []):
        key = (m.get("Namespace", ""), m.get("MetricName", ""))
        if key not in seen:
            seen.add(key)
            metrics.append({
                "namespace": key[0],
                "name": key[1],
            })
    return metrics
