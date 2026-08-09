import datetime
import os
import boto3
import click

SESSION = boto3.Session(profile_name="platform-cli")
ALLOWED_INSTANCE_TYPES = ["t3.micro", "t2.small"]

@click.group()
def cli():
    pass

@cli.group()
def ec2():
    pass

@cli.group()
def s3():
    pass

@cli.group()
def route53():
    pass


@ec2.command()
@click.option("--instance-type", type=click.Choice(ALLOWED_INSTANCE_TYPES))
@click.option("--owner", required=True)
def create(instance_type, owner):
    response = create_ec2_instance(instance_type, owner)
    if response is None:
        click.echo("Error: cannot create more than 2 running instances")
        return
    click.echo(f"Creating instance: {response}")

@ec2.command()
def list():
    instances = list_ec2_instances()
    if not instances:
        click.echo("No instances found")
        return
    for instance in instances:
        click.echo(f"Instances running: {instance['InstanceId']} {instance['State']['Name']}")


@ec2.command()
@click.option("--instance-id", required=True)
def start(instance_id):
    result = start_ec2_instance(instance_id)
    if isinstance(result, str):
        click.echo(result)
        return
    click.echo(f"Instance started: {result}")


@ec2.command()
@click.option("--instance-id", required=True)
def stop(instance_id):
    result = stop_ec2_instance(instance_id)
    if isinstance(result, str):
        click.echo(result)
        return
    click.echo(f"Instance stopped: {result}")


@s3.command()
@click.option("--bucket-name", required=True)
@click.option("--file-path", required=True)
def upload(bucket_name, file_path):
    result = upload_file_to_bucket(bucket_name, file_path)
    if isinstance(result, str):
        click.echo(result)
        return
    click.echo(f"Successfully uploaded {file_path} to bucket: {bucket_name}")

@s3.command()
@click.option("--bucket-name", required=True)
@click.option("--visibility", type=click.Choice(["public", "private"]), required=True)
@click.option("--owner", required=True)
def create(bucket_name, visibility, owner):
    if visibility == "public":
        if click.confirm("Do you want to create public yes/no"):
            click.echo("Creating public bucket")
        else:
            click.echo("Not creating public bucket")
            return
    response = create_s3_bucket(bucket_name, owner, visibility)
    click.echo(f"Creating bucket: {bucket_name} (owner: {owner})")


@s3.command()
def list():
    buckets = list_s3_buckets()
    if not buckets:
        click.echo("No buckets found")
        return
    for bucket in buckets:
        click.echo(f"Bucket found: {bucket}")


@route53.command()
@click.option("--domain-name", required=True)
@click.option("--owner", required=True)
def create_zone(domain_name, owner):
    response = create_hosted_zone(domain_name)
    zone_id = response["HostedZone"]["Id"]
    clean_zone_id = zone_id.replace("/hostedzone/", "")
    tag_hosted_zone(clean_zone_id, owner)
    click.echo(f"Created hosted zone: {clean_zone_id} by owner: {owner}")


@route53.command()
@click.option("--zone-id", required=True)
@click.option("--action", type=click.Choice(["CREATE", "UPSERT", "DELETE"]), required=True)
@click.option("--record-name", required=True)
@click.option("--record-type", required=True)
@click.option("--record-value", required=True)
def manage_record(zone_id, action, record_name, record_type, record_value):
    response = manage_dns_record(zone_id, action, record_name, record_type, record_value)
    click.echo(f"Dns record {action} completed record: {response}")


@route53.command()
def list():
    zones = list_route53_zones()
    if not zones:
        click.echo("No route53 zones found")
        return
    for zone in zones:
        click.echo(f"Route53 found: {zone}")


#EC2 ----------instance-----------
def count_running_instances():
    ec2_client = SESSION.client("ec2")
    response = ec2_client.describe_instances(
        Filters=[
            {"Name": "tag:CreatedBy", "Values": ["platform-cli"]},
            {"Name": "tag:Owner", "Values": ["alex"]},
            {"Name": "instance-state-name", "Values": ["running", "pending"]}
        ]
    )
    instances = []
    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            instances.append(instance)
    return len(instances)

def build_tags(owner):
    return [
        {"Key": "CreatedBy", "Value": "platform-cli"},
        {"Key": "Owner", "Value": owner}
    ]


def get_latest_ami(os_choice):
    ssm_client = SESSION.client("ssm")
    if os_choice == "ubuntu":
        parameter_name = "/aws/service/canonical/ubuntu/server/26.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
    elif os_choice == "amazon-linux":
        parameter_name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
    response = ssm_client.get_parameter(Name=parameter_name)
    return response["Parameter"]["Value"]


def create_ec2_instance(instance_type, owner):
    ec2_client = SESSION.client("ec2")
    if count_running_instances() >= 2:
        return None
    ami_id = get_latest_ami("ubuntu")
    tags = build_tags(owner)
    response = ec2_client.run_instances(
        ImageId = ami_id,
        InstanceType = instance_type,
        MinCount = 1,
        MaxCount = 1,
        TagSpecifications = [
            {"ResourceType": "instance", "Tags": tags}
        ]
    )
    return response


def is_cli_instance(instance_id):
    cli_instance = list_ec2_instances()
    for instance in cli_instance:
        if instance["InstanceId"] == instance_id:
            return True
    return False


def stop_ec2_instance(instance_id):
    if not is_cli_instance(instance_id):
        return "Not CLI managed instance"
    ec2_client = SESSION.client("ec2")
    response = ec2_client.stop_instances(InstanceIds=[instance_id])
    return response


def start_ec2_instance(instance_id):
    if not is_cli_instance(instance_id):
        return "Not CLI managed instance"
    ec2_client = SESSION.client("ec2")
    response = ec2_client.start_instances(InstanceIds=[instance_id])
    return response


def list_ec2_instances():
    ec2_client = SESSION.client("ec2")
    response = ec2_client.describe_instances(
        Filters=[
            {"Name": "tag:CreatedBy", "Values": ["platform-cli"]},
            {"Name": "tag:Owner", "Values": ["alex"]},
        ]
    )
    instances = []
    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            instances.append(instance)
    return instances

#S3 ------------Bucket-----------
def create_s3_bucket(bucket_name, owner, visibility):
    s3_client = SESSION.client("s3", region_name="us-east-1")

    response = s3_client.create_bucket(
        Bucket=bucket_name,
    )
    tags = build_tags(owner)
    s3_client.put_bucket_tagging(
        Bucket=bucket_name,
        Tagging={"TagSet": tags}
    )
    if visibility == "private":
        block_setting = True
    else:
        block_setting = False
    s3_client.put_public_access_block(
        Bucket=bucket_name,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": block_setting,
            "IgnorePublicAcls": block_setting,
            "BlockPublicPolicy": block_setting,
            "RestrictPublicBuckets": block_setting,
        }
    )
    return response

def upload_file_to_bucket(bucket_name, file_path):
    cli_buckets = list_s3_buckets()
    if bucket_name not in cli_buckets:
        return "Not a CLI-managed bucket"
    s3_client = SESSION.client("s3")
    response = s3_client.upload_file(file_path, bucket_name, os.path.basename(file_path))
    return response


def list_s3_buckets():
    s3_client = SESSION.client("s3")
    all_buckets = s3_client.list_buckets()

    cli_buckets = []
    for bucket in all_buckets["Buckets"]:
        bucket_name = bucket["Name"]
        try:
            tag_response = s3_client.get_bucket_tagging(Bucket=bucket_name)
            tags = tag_response["TagSet"]
            has_created_by = False
            has_owner = False
            for tag in tags:
                if tag["Key"] == "CreatedBy" and tag["Value"] == "platform-cli":
                    has_created_by = True
                if tag["Key"] == "Owner" and tag["Value"] == "alex":
                    has_owner = True
            if has_created_by and has_owner:
                    cli_buckets.append(bucket_name)
        except:
            pass
    return cli_buckets


#Route53 -------------Zone----------------
def create_hosted_zone(domain_name):
    route53_client = SESSION.client("route53")
    caller_reference = datetime.datetime.now().strftime("%Y-%m-%d %H:%M%S")
    response = route53_client.create_hosted_zone(
        Name=domain_name,
        CallerReference=caller_reference
    )
    return response


def manage_dns_record(zone_id, action, record_name, record_type, record_value):
    route53_client = SESSION.client("route53")

    response = route53_client.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            "Changes": [
                {
                    "Action": action,
                    "ResourceRecordSet": {
                        "Name": record_name,
                        "Type": record_type,
                        "TTL": 300,
                        "ResourceRecords": [{"Value": record_value}]
                    }
                }
            ]
        }
    )
    return response


def tag_hosted_zone(zone_id, owner):
    route53_client = SESSION.client("route53")
    tags = build_tags(owner)

    response = route53_client.change_tags_for_resource(
        ResourceType="hostedzone",
        ResourceId=zone_id,
        AddTags=tags
    )
    return response




def list_route53_zones():
    route53_client = SESSION.client("route53")
    all_zones = route53_client.list_hosted_zones()

    cli_zones = []
    for zone in all_zones["HostedZones"]:
        zone_id = zone["Id"]
        clean_zone_id = zone_id.replace("/hostedzone/", "")
        try:
            tag_response = route53_client.list_tags_for_resource(
                ResourceType='hostedzone',
                ResourceId=clean_zone_id
            )
            tags = tag_response["ResourceTagSet"]["Tags"]
            has_created_by = False
            has_owner = False
            for tag in tags:
                if tag["Key"] == "CreatedBy" and tag["Value"] == "platform-cli":
                    has_created_by = True
                if tag["Key"] == "Owner" and tag["Value"] == "alex":
                    has_owner = True
            if has_created_by and has_owner:
                    cli_zones.append(clean_zone_id)
        except:
            pass
    return cli_zones


if __name__ == "__main__":
    cli()
