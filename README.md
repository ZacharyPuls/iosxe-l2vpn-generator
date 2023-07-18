# iosxe-l2vpn-generator
Python script I developed to auto-provision L2VPNs on lab ASR-920 routers in bulk, in order to test certain scale/feature limitations on new software loads.

# Running
- I recommend running this in a virtual environment. Create one via `python -m venv ./venv`, then activate it using `venv/Scripts/activate(.bat)`.
- Install the pip requirements with `pip install -r requirements.txt`
- Edit base.j2 to conform to your circuit labeling standards and/or requirements.
- Edit the sample .env to provide the username/password that has read/write access to your lab devices.
- Execute the script with `python main.py --help`, which displays the usage.

# Features currently supported
- Provision *n* test L2VPNs
- Deprovision all test L2VPNs
- Generate *n* test L2VPNs, but only output the config to a file ("dry-run")