import streamlit as st
from cli import create_ec2_instance, list_ec2_instances, start_ec2_instance, stop_ec2_instance
from cli import create_s3_bucket, list_s3_buckets, upload_file_to_bucket
from cli import create_hosted_zone, tag_hosted_zone, manage_dns_record, list_route53_zones

st.title("Platform CLI")
st.write("Hello from Streamlit")

st.header("Create EC2 Instance")
instance_type = st.selectbox("Instance Type", ["t3.micro", "t2.small"])
owner =  st.text_input("Owner")

if st.button("Create Instance"):
    result = create_ec2_instance(instance_type, owner)
    if result is None:
        st.error("Cannot create more than 2 running instances")
    else:
        st.success(f"Instance created: {result['Instances'][0]['InstanceId']}")


st.header("List EC2 Instances")
if st.button("List Instances"):
    instacnes = list_ec2_instances()
    if not instacnes:
        st.error("No instances found")
    else:
        for instance in instacnes:
            st.write(f"Name: {instance['InstanceId']} - {instance['State']['Name']}")


st.header("Start/Stop EC2 Instance")
instance_id = st.text_input("Instance ID")

if st.button("Start Instance"):
    result = start_ec2_instance(instance_id)
    if isinstance(result, str):
        st.warning(result)
    else:
        st.success(f"Instance started: {instance_id}")

if st.button("Stop Instance"):
    result = stop_ec2_instance(instance_id)
    if isinstance(result, str):
        st.warning(result)
    else:
        st.success(f"Instance stopped: {instance_id}")


st.header("Create S3 Bucket")
bucket_name = st.text_input("Bucket Name")
visibility = st.radio("Visibility", ["public", "private"])
s3_owner = st.text_input("Owner (S3)")

confirmed = True
if visibility == "public":
    confirmed = st.checkbox("Are you sure creating a PUBLIC bucket?")

if st.button("Create Bucket"):
    if not confirmed:
        st.warning("Didn't confirm not creating a PUBLIC bucket")
    else:
        response = create_s3_bucket(bucket_name, s3_owner, visibility)
        st.success(f"Bucket created: {bucket_name}")

st.header("List S3 Buckets")
if st.button("List Buckets"):
    buckets = list_s3_buckets()
    if not buckets:
        st.write("No buckets found")
    else:
        for bucket in buckets:
            st.write(bucket)

st.header("Upload File to S3")
upload_bucket_name = st.text_input("Bucket Name (for upload)")
uploaded_file = st.file_uploader("Choose a file")

if st.button("Upload File"):
    if uploaded_file is not None:
        with open(uploaded_file.name, "wb") as f:
            f.write(uploaded_file.getbuffer())
        result = upload_file_to_bucket(upload_bucket_name, uploaded_file.name)
        if isinstance(result, str):
            st.warning(result)
        else:
            st.success(f"Uploaded {uploaded_file.name} to {upload_bucket_name}")

st.header("Create Route53 Hosted Zone")
domain_name = st.text_input("Domain Name")
zone_owner = st.text_input("Owner (Route53)")

if st.button("Create Hosted Zone"):
    response = create_hosted_zone(domain_name)
    zone_id = response["HostedZone"]["Id"]
    clean_zone_id = zone_id.replace("/hostedzone/", "")
    tag_hosted_zone(clean_zone_id, zone_owner)
    st.success(f"Hosted zone created: {clean_zone_id}")

st.header("List Route53 Zones")
if st.button("List Zones"):
    zones = list_route53_zones()
    if not zones:
        st.write("No zones found")
    else:
        for zone in zones:
            st.write(zone)

st.header("Manage DNS Record")
record_zone_id = st.text_input("Zone ID")
action = st.selectbox("Action", ["CREATE", "UPDATE", "DELETE"])
record_name = st.text_input("Record Name")
record_type = st.selectbox("Record Type", ["A", "CNAME", "MX"])
record_value = st.text_input("Record Value")

if st.button("Submit Record Change"):
    response = manage_dns_record(record_zone_id, action, record_name, record_type, record_value)
    st.success(f"DNS record {action} completed")
