from argparse import ArgumentParser
from netmiko import ConnectHandler
from datetime import datetime
from dotenv import load_dotenv
from dataclasses import dataclass, asdict
from itertools import chain, filterfalse
from jinja2 import Environment, FileSystemLoader
from typing import Tuple
import os
import re


@dataclass
class L2VPN:
    circuit_id: int
    vcid: str
    interface: str
    vlan: int
    peer_router_loopback_ip_address: str
    source_mpid: int
    target_mpid: int
    slm_ip_sla_id: int
    dmm_ip_sla_id: int
    ccm_interval: str = '10s'
    cfm_domain: str = 'OPERATOR'
    cfm_level: int = 1


def get_next_available_efp_id(a_device: ConnectHandler, a_interface: str, z_device: ConnectHandler, z_interface: str) -> int:
    efp_id_regex = r'\s+service instance (\d+) ethernet .*'

    a_output = a_device.send_command(f'show running-config interface {a_interface} | include service instance')
    a_efp_id_matches = re.findall(efp_id_regex, a_output)
    a_all_efp_ids = set([int(efp_id) for efp_id in a_efp_id_matches])

    z_output = z_device.send_command(f'show running-config interface {z_interface} | include service instance')
    z_efp_id_matches = re.findall(efp_id_regex, z_output)
    z_all_efp_ids = set([int(efp_id) for efp_id in z_efp_id_matches])

    used_efp_ids = chain(a_all_efp_ids, z_all_efp_ids)

    return next(filterfalse(lambda efp_id: efp_id in used_efp_ids, range(1, 4094)))


def get_next_available_two_ip_sla_ids(a_device: ConnectHandler, z_device: ConnectHandler) -> Tuple[int, int]:
    ip_sla_id_show_command = 'show running-config | include ^ip sla [0-9]'
    ip_sla_id_regex = r'ip sla (\d+)'

    a_output = a_device.send_command(ip_sla_id_show_command)
    a_ip_sla_id_matches = re.findall(ip_sla_id_regex, a_output)
    a_all_ip_sla_ids = set([int(ip_sla_id) for ip_sla_id in a_ip_sla_id_matches])

    z_output = z_device.send_command(ip_sla_id_show_command)
    z_ip_sla_id_matches = re.findall(ip_sla_id_regex, z_output)
    z_all_ip_sla_ids = set([int(ip_sla_id) for ip_sla_id in z_ip_sla_id_matches])

    used_ip_sla_ids = chain(a_all_ip_sla_ids, z_all_ip_sla_ids)

    filtered_ip_sla_ids = filterfalse(lambda ip_sla_id: ip_sla_id in used_ip_sla_ids, range(1, 2147483647))
    slm_ip_sla_id: int = next(filtered_ip_sla_ids)
    dmm_ip_sla_id: int = next(filtered_ip_sla_ids)

    return [slm_ip_sla_id, dmm_ip_sla_id]


def main():
    parser = ArgumentParser(
        prog='TestCircuitGenerator',
        description='Generates and provisions (or deprovisions) *n* test L2VPNs on a pair of IOS-XE devices'
    )
    subparsers = parser.add_subparsers(help='Which action to perform', dest='subcommand')
    
    provision = subparsers.add_parser('provision', help='Provision *n* test L2VPNs on the provided IOS-XE devices')
    provision.add_argument('a_device_ip_address', help='Provision the test L2VPN(s) using this IPv4 address as the A device')
    provision.add_argument('z_device_ip_address', help='Provision the test L2VPN(s) using this IPv4 address as the Z device')
    provision.add_argument('n', type=int)
    provision.add_argument('--a-loopback', help='Provision the test L2VPN(s) using this IPv4 address as the A device Loopback', dest='a_device_loopback_ip_address')
    provision.add_argument('--z-loopback', help='Provision the test L2VPN(s) using this IPv4 address as the Z device Loopback IP', dest='z_device_loopback_ip_address')
    provision.add_argument('--a-interface', help='Provision the test L2VPN(s) on the A device under this interface', dest='a_device_interface')
    provision.add_argument('--z-interface', help='Provision the test L2VPN(s) on the Z device under this interface', dest='z_device_interface')
    provision.add_argument('--dry-run', help='Don\'t provision the test L2VPN(s), just write the configuration that would be applied to the respective device filenames', dest='dry_run', action='store_true')

    deprovision = subparsers.add_parser('deprovision', help='Deprovision all previously provisioned test L2VPNs on the provided IOS-XE devices')
    deprovision.add_argument('a_device_ip_address', help='Deprovision all previously provisioned test L2VPNs using this IPv4 address as the A device')
    deprovision.add_argument('z_device_ip_address', help='Deprovision all previously provisioned test L2VPNs using this IPv4 address as the Z device')

    args = parser.parse_args()

    if not load_dotenv() or not os.getenv('username') or not os.getenv('password'):
        print('Failed to load .env file. Please create a .env file with the following parameters:\n\tusername: The user account that has access to log into the lab device(s) via SSH\n\tpassword: The password for the above user account.\n')
        return

    startTime = datetime.now()

    a_device_options = {
        'device_type': 'cisco_xe',
        'host': args.a_device_ip_address,
        'username': os.getenv('username'),
        'password': os.getenv('password'),
        'fast_cli': True
    }

    z_device_options = {
        'device_type': 'cisco_xe',
        'host': args.z_device_ip_address,
        'username': os.getenv('username'),
        'password': os.getenv('password'),
        'fast_cli': True
    }

    a_device = ConnectHandler(**a_device_options)
    z_device = ConnectHandler(**z_device_options)

    environment = Environment(loader=FileSystemLoader('.'))
    a_device_deprovision_filename = f'{args.a_device_ip_address}_removal.cfg'
    z_device_deprovision_filename = f'{args.z_device_ip_address}_removal.cfg'
    a_device_dry_run_filename = f'{args.a_device_ip_address}_dry-run.cfg'
    z_device_dry_run_filename = f'{args.z_device_ip_address}_dry-run.cfg'

    if args.subcommand == 'provision':
        l2vpn_template = environment.get_template('l2vpn.j2')
        l2vpn_deprovision_template = environment.get_template('l2vpn_deprovision.j2')

        for i in range(args.n):
            ip_sla_ids = get_next_available_two_ip_sla_ids(a_device, z_device)
            slm_id=ip_sla_ids[0]
            dmm_id=ip_sla_ids[1]
            vlan: int = get_next_available_efp_id(a_device, args.a_device_interface, z_device, args.z_device_interface)
            vlan_padded: str = '{:04d}'.format(vlan)
            vcid: str = f'500{vlan_padded}'
            circuit_id: str = vlan_padded

            a_l2vpn = L2VPN(circuit_id=circuit_id, vcid=vcid, interface=args.a_device_interface, vlan=vlan, peer_router_loopback_ip_address=args.z_device_loopback_ip_address, source_mpid=1, target_mpid=2, slm_ip_sla_id=slm_id, dmm_ip_sla_id=dmm_id)
            a_config: str = l2vpn_template.render(asdict(a_l2vpn))
            z_l2vpn = L2VPN(circuit_id=circuit_id, vcid=vcid, interface=args.z_device_interface, vlan=vlan, peer_router_loopback_ip_address=args.a_device_loopback_ip_address, source_mpid=2, target_mpid=1, slm_ip_sla_id=slm_id, dmm_ip_sla_id=dmm_id)
            z_config: str = l2vpn_template.render(asdict(z_l2vpn))

            if args.dry_run:
                with open(a_device_dry_run_filename, mode='a') as a_device_dry_run_file:
                    a_device_dry_run_file.write(a_config)

                with open(z_device_dry_run_filename, mode='a') as z_device_dry_run_file:
                    z_device_dry_run_file.write(z_config)
            else:
                a_device.send_config_set(a_config.split('\n'), read_timeout=60)
                a_device_deprovision_config: str = l2vpn_deprovision_template.render(asdict(a_l2vpn)) + '\n'

                z_device.send_config_set(z_config.split('\n'), read_timeout=60)
                z_device_deprovision_config: str = l2vpn_deprovision_template.render(asdict(z_l2vpn)) + '\n'

                with open(a_device_deprovision_filename, mode='a') as a_device_deprovision_file:
                    a_device_deprovision_file.write(a_device_deprovision_config)

                with open(z_device_deprovision_filename, mode='a') as z_device_deprovision_file:
                    z_device_deprovision_file.write(z_device_deprovision_config)
                
    elif args.subcommand == 'deprovision':
        with open(a_device_deprovision_filename) as a_device_deprovision_file:
            a_config = a_device_deprovision_file.read().split('\n')
            a_device.send_config_set(a_config, read_timeout=60)
        os.remove(a_device_deprovision_filename)
        with open(z_device_deprovision_filename) as z_device_deprovision_file:
            z_config = z_device_deprovision_file.read().split('\n')
            z_device.send_config_set(z_config, read_timeout=60)
        os.remove(z_device_deprovision_filename)

    a_device.disconnect()
    z_device.disconnect()

    print(f'Script took {datetime.now() - startTime} to run.')


if __name__ == '__main__':
    main()