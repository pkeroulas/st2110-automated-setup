#!/usr/bin/env python

import logging
import yaml
import pynetbox
import hashlib
import re
import copy
import os
from netaddr import *
from ansible.module_utils.basic import AnsibleModule

MODULE_LOGGER = logging.getLogger('get_netbox_data')
MODULE_LOGGER.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(message)s')
file_handler = logging.FileHandler('../roles/netbox/get_netbox_data.log')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
MODULE_LOGGER.addHandler(file_handler)
MODULE_LOGGER.info('Start get_netbox_data module execution')

yaml.preserve_quotes = True

class IndentDumper(yaml.Dumper):
  def increase_indent(self, flow=False, indentless=False):
    return super(IndentDumper, self).increase_indent(flow, False)

def write_yaml_file(filename, yaml_dict, sort=True):
  with open(filename, 'w') as f:
    yaml.dump(yaml_dict, f, default_flow_style=False, indent=2, sort_keys=sort)

def open_yaml_file(filename):
  if not os.path.isfile(filename):
    yaml_dict = {}
    write_yaml_file(filename, yaml_dict, sort=True)
    return yaml_dict

  with open(filename, 'r') as stream:
    try:
      return yaml.safe_load(stream)
    except yaml.YAMLError as exc:
      print(exc)
      return None

def hash_yaml_file(filename):
  hash_md5 = hashlib.md5()
  try:
    with open(filename, 'rb') as inputfile:
      data = inputfile.read()
      hash_md5.update(data)
  except Exception as e:
    print('no-file {}',e)
  return hash_md5.hexdigest()

SW_STRUCTURE_PORT_TEMPLATE = {
  "description": "_",
  "shutdown": False,
  "speed": "forced 10gfull",
  "error_correction_encoding": {
    "enabled": False
  },
  "type": "switched",
  "spanning_tree_portfast": "edge",
  "ptp": {
    "enable": True,
    "announce": {
      "interval": 0
    },
    "delay_req": -3,
    "sync_message": {
      "interval": -3
    },
    "role": "master"
  }
}

def process_switch(nb, struct_config, nb_dev):
  nb_ifaces = list(nb.dcim.interfaces.filter(device=nb_dev.name))
  for nb_iface in nb_ifaces:
    if nb_iface.name == 'Ethernet48' or nb_iface.name == 'Management1': # Never touch the management link,
      continue

    # add missing
    if not nb_iface.name in struct_config['ethernet_interfaces']:
      struct_config['ethernet_interfaces'][nb_iface.name] = copy.deepcopy(SW_STRUCTURE_PORT_TEMPLATE)

    struct_iface = struct_config['ethernet_interfaces'][nb_iface.name]
    struct_iface['description'] = nb_iface.description if nb_iface.description != '' else '_'
    MODULE_LOGGER.info(f"{ nb_iface.name } IN ({ nb_iface.mode })")

    #VLANS
    if nb_iface.mode == None: # delete iface
      if "mode" in struct_iface.keys(): del struct_iface['mode']
      if "vlans" in struct_iface.keys(): del struct_iface['vlans']
    elif nb_iface.mode.value == 'access': # add access
      struct_iface['mode'] = nb_iface.mode.value
      struct_iface['vlans'] = nb_iface.untagged_vlan.vid
    elif nb_iface.mode.value == 'tagged': # add trunk
      struct_iface['mode'] = 'trunk'
      structured_vids = ''
      for vlan in nb_iface.tagged_vlans:
        structured_vids += f"{ vlan.vid },"
      struct_iface['vlans'] = structured_vids[:-1] #remove last ','
      if nb_iface.untagged_vlan != None:
        MODULE_LOGGER.info(f"What TODO with { nb_iface.untagged_vlan }")

  return struct_config

GW_STRUCTURE_TEMPLATE = {
  "status": "inventory",
  "host_ip": "",
  "mac": "",
  "hostname": "",
  "description": "",
  "role": "",
  "config_context": { }
}

def get_mac_address(nb, ip_id):
  nb_ip = nb.ipam.ip_addresses.get(ip_id)
  nb_iface = nb.dcim.interfaces.get(nb_ip.assigned_object_id)
  if nb_iface == None:
    MODULE_LOGGER.info(f"Error while retrieving iface from ip address { ip }: { nb_ips }")
  return nb_iface.mac_address

def process_gateway(nb, struct_config, nb_dev):
  struct_config = copy.deepcopy(GW_STRUCTURE_TEMPLATE)
  struct_config['hostname'] = nb_dev.name
  struct_config['device_role'] = nb_dev.device_role.slug
  struct_config['status'] = nb_dev.status.value
  if nb_dev.description != "":
    struct_config['description'] = nb_dev.description
  if nb_dev.primary_ip != None:
    struct_config['host_ip'] = str(IPNetwork(nb_dev.primary_ip.address).ip)
    struct_config['mac'] = get_mac_address(nb, nb_dev.primary_ip.id)
  struct_config['config_context'] =  nb_dev.config_context
  return struct_config

def main():
  module = AnsibleModule(
    argument_spec=dict(
      nb_host=dict(type='str', required=True),
      token=dict(type='str', required=True),
      config_dir=dict(type='str', required=True),
      target_type=dict(type='str', required=True),
      inventory_hostname=dict(type='str', required=False),
    ),
    supports_check_mode=True,
  )
  nb_host = module.params['nb_host']
  token = module.params['token']
  config_dir  = module.params['config_dir']
  target_type  = module.params['target_type']
  nb = pynetbox.api(nb_host,token)
  nb.http_session.verify = False

  hash_init = hash_end = has_changed = False

  if target_type == 'endpoints':
    config_file = f"{ config_dir }/hosts.yml"
    struct_config = open_yaml_file(config_file)
    MODULE_LOGGER.info(f"GW IN {struct_config}")
    if struct_config == None:
      module.exit_json(changed=has_changed, msg=f"EXIT 1")
    hash_init = hash_yaml_file(config_file)

    hosts = struct_config['all']['children']['DC']['hosts']

    for host in hosts.keys():
      nb_devices = nb.dcim.devices.filter(name=host)
      if len(nb_devices) == 0:
        continue

      nb_dev = nb_devices[0]
      struct_config_dev = hosts[host]
      hosts[host] = process_gateway(nb, struct_config_dev, nb_dev)
      MODULE_LOGGER.info(f"GW { host } { hosts }")

    struct_config['all']['children']['DC']['hosts'] = hosts

  elif target_type == 'switch':
    inventory_hostname  = module.params['inventory_hostname']
    config_file = f"{ config_dir }/{ inventory_hostname }.yml"
    hash_init = hash_yaml_file(config_file)
    nb_devices = nb.dcim.devices.filter(name=inventory_hostname)
    if len(nb_devices) == 0:
      module.exit_json(changed=has_changed, msg=f"EXIT 0")
    nb_dev = nb_devices[0]
    struct_config = open_yaml_file(config_file)
    struct_config = process_switch(nb, struct_config, nb_dev)

  write_yaml_file(config_file, struct_config, False)
  hash_end = hash_yaml_file(config_file)
  MODULE_LOGGER.info(f"{config_file}: HASH { hash_init } -> { hash_end }")
  has_changed = has_changed if hash_init == hash_end else True

  module.exit_json(changed=has_changed, msg=f"Received from NetBox, url= {module.params['nb_host']}")

if __name__ == "__main__":
  main()
