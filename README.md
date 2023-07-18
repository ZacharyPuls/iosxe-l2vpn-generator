# iosxe-l2vpn-generator
Python script I developed to auto-provision L2VPNs on lab ASR-920 routers in bulk, in order to test certain scale/feature limitations on new software loads.

# Prerequisites
This script assumes you have a pair of IOS-XE devices running a recent software load (in my case, I used a pair of ASR-920-24SZ-M routers running IOS-XE 17.6.3). The devices should have layer 2 connectivity established, with an IGP providing layer 3 continuity between the loopback IPv4 addresses, and MPLS+LDP running. The following class-map should be provisioned on both devices as well:
```
class-map match-all CLASS-PLACEHOLDER-EGRESS
 match qos-group 20
```

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