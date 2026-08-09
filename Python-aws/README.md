Platform CLI

A Python command-line tool (with an optional Streamlit UI) for creating and managing AWS resources — EC2 instances, S3 buckets, and Route53 DNS zones/records — with built-in safety constraints and consistent tagging.
Every resource created by this tool is tagged so the tool only ever lists, starts, stops, or modifies resources it created itself — never anything else in the AWS account.

What This Tool Does
EC2: create instances (t3.micro or t2.small only, latest Ubuntu AMI via SSM), list your instances, start/stop them — enforces a hard cap of 2 running instances at a time.
S3: create buckets as public or private (public requires explicit confirmation), upload files, list your buckets — private buckets are locked down with S3's Public Access Block by default.
Route53: create hosted zones, create/update/delete DNS records, list your zones.

All resources are tagged with CreatedBy=platform-cli and Owner=<your name>, and every command validates these tags before acting — so the tool never touches resources it didn't create, even in a shared AWS account.
Prerequisites
Python 3.10+
An AWS account with an IAM user (not root) that has permissions for EC2, S3, Route53, and SSM (read-only is enough for SSM)
An AWS profile configured locally, named platform-cli
Setting up the AWS profile

If you have the AWS CLI installed:
aws configure --profile platform-cli

If not, create the files manually:
~/.aws/credentials (on Windows: C:\Users\<you>\.aws\credentials):\
ini
[platform-cli]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY
~/.aws/config:
ini
[profile platform-cli]
region = us-east-1
output = json
This tool is hardcoded to the us-east-1 region. Each person running it needs to set up their own credentials under this same platform-cli profile name — no credentials are ever stored in this repository.

Installation
python -m venv .venv
source .venv/bin/activate      # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
Usage — CLI

Run python cli.py --help to see all commands.
EC2
# Create an instance (instance-type must be t3.micro or t2.small)
python cli.py ec2 create --instance-type t3.micro --owner alex

# List only CLI-created instances
python cli.py ec2 list

# Start / stop a CLI-created instance
python cli.py ec2 start --instance-id i-0123456789abcdef0
python cli.py ec2 stop --instance-id i-0123456789abcdef0

Creation is blocked once you have 2 instances running (or launching) — you'll see: Error: cannot create more than 2 running instances
S3
# Create a private bucket
python cli.py s3 create --bucket-name my-bucket-name --visibility private --owner alex

# Create a public bucket (asks for confirmation)
python cli.py s3 create --bucket-name my-public-bucket --visibility public --owner alex
# -> Do you want to create public yes/no [y/N]:

# Upload a file (only works on CLI-created buckets)
python cli.py s3 upload --bucket-name my-bucket-name --file-path ./myfile.txt

# List only CLI-created buckets
python cli.py s3 list
Route53
# Create a hosted zone
python cli.py route53 create-zone --domain-name example.com --owner alex

# Create / update / delete a DNS record (use the zone ID from create-zone)
python cli.py route53 manage-record --zone-id Z0123456789ABC --action CREATE --record-name www.example.com --record-type A --record-value 1.2.3.4
python cli.py route53 manage-record --zone-id Z0123456789ABC --action UPSERT --record-name www.example.com --record-type A --record-value 5.6.7.8
python cli.py route53 manage-record --zone-id Z0123456789ABC --action DELETE --record-name www.example.com --record-type A --record-value 5.6.7.8

# List only CLI-created zones
python cli.py route53 list
Usage — Web UI (Phase 2, Streamlit)

A basic web UI is available covering the same functionality as the CLI, built on top of the same underlying functions.
streamlit run app.py

This opens a browser tab with forms for creating/listing/managing EC2 instances, S3 buckets, and Route53 zones/records — the same safety checks (instance cap, tag validation, public-bucket confirmation) apply, since the UI calls the exact same functions as the CLI.
Tagging Convention
Every resource created by this tool receives:
Tag	Value
CreatedBy	platform-cli
Owner	whatever --owner value you provide
All list, start, stop, and upload operations filter by both tags — not just CreatedBy — so that in a shared AWS account, each user only ever sees and manages their own resources.

Known Limitations
EC2 cap and instant successive creates: AWS instances briefly sit in a pending state before becoming running. The cap check counts both pending and running instances to close this gap, but there is inherently a small race-condition window with any tag-based, client-side cap check (as opposed to an atomic, AWS-side limit).
Region is hardcoded to us-east-1 — the tool does not currently support creating resources in other regions.
Route53 hosted zone IDs: AWS returns zone IDs with a /hostedzone/ prefix from some API calls; this tool strips it internally so IDs shown to the user are always in the short form (e.g. Z0123456789ABC).
Cleanup Instructions

To avoid ongoing AWS costs, clean up test resources when you're done:
EC2 — stop instances you no longer need:
python cli.py ec2 stop --instance-id <id>
To fully remove them, terminate via the AWS Console or AWS CLI (aws ec2 terminate-instances --instance-ids <id>) — this tool does not currently expose a terminate command.

S3 — buckets must be emptied before deletion. Via AWS CLI:
aws s3 rm s3://<bucket-name> --recursive
aws s3api delete-bucket --bucket <bucket-name>

Route53 — hosted zones incur a small monthly charge even when unused. Delete via AWS CLI once all non-default records are removed:
aws route53 delete-hosted-zone --id <zone-id>

Security Notes
No AWS credentials are stored in this repository (.gitignore excludes .venv/, IDE files, and cache directories).
All AWS access goes through a named profile (platform-cli) configured locally by each user — never hardcoded keys.
S3 buckets default to private, with S3's Public Access Block fully enabled; public buckets require explicit interactive confirmation.