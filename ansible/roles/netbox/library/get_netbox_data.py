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

def process_switch(nb, struct_config, dev):
  nb_ifaces = list(nb.dcim.interfaces.filter(device=dev.name))
  for nb_iface in nb_ifaces:
    if nb_iface.name == 'Ethernet48' or nb_iface.name == 'Management1': # Never touch the management link,
      continue

    # add missing
    if not nb_iface.name in struct_config['ethernet_interfaces']:
      struct_config['ethernet_interfaces'][nb_iface.name] = copy.deepcopy(SW_STRUCTURE_PORT_TEMPLATE)

    structured_iface = struct_config['ethernet_interfaces'][nb_iface.name]
    structured_iface['description'] = nb_iface.description if nb_iface.description != '' else '_'
    MODULE_LOGGER.info(f"{ nb_iface.name } ({ nb_iface.description })")

    #VLANS
    if nb_iface.mode == None: # delete iface
        if hasattr(structured_iface, "mode"): del structured_iface['mode']
        if hasattr(structured_iface, "vlans"): del structured_iface['vlans']
    elif nb_iface.mode.value == 'access': # add access
      structured_iface['mode'] = nb_iface.mode.value
      structured_iface['vlans'] = nb_iface.untagged_vlan.vid
    elif nb_iface.mode.value == 'tagged': # add trunk
      structured_iface['mode'] = 'trunk'
      structured_vids = ''
      for vlan in nb_iface.tagged_vlans:
        structured_vids += f"{ vlan.vid },"
      structured_iface['vlans'] = structured_vids[:-1] #remove last ','
      if nb_iface.untagged_vlan != None:
        MODULE_LOGGER.info(f"What TODO with { nb_iface.untagged_vlan }")

  return struct_config

GW_STRUCTURE_PORT_TEMPLATE = {
  "host_ip": "",
  "hostname": "",
  "description": "",
  "role": "",
  "config_context": { }
}

def process_gateway(nb, struct_config, dev):
  struct_config = GW_STRUCTURE_PORT_TEMPLATE
  struct_config['hostname'] = dev.name
  struct_config['role'] = dev.device_role.slug
  if dev.description != "":
    struct_config['description'] = dev.description
  if dev.primary_ip != None:
    struct_config['host_ip'] = str(IPNetwork(dev.primary_ip.address).ip)
  struct_config['config_context'] =  dev.config_context
  return struct_config

def main():
  module = AnsibleModule(
    argument_spec=dict(
      nb_host=dict(type='str', required=True),
      token=dict(type='str', required=True),
      config_dir=dict(type='str', required=True),
      device_role=dict(type='str', required=True),
      inventory_hostname=dict(type='str', required=True),
    ),
    supports_check_mode=True,
  )
  nb_host = module.params['nb_host']
  token = module.params['token']
  config_dir  = module.params['config_dir']
  device_role  = module.params['device_role']
  inventory_hostname  = module.params['inventory_hostname']
  nb = pynetbox.api(nb_host,token)
  nb.http_session.verify = False

  hash_init = hash_end = has_changed = False
  devices = nb.dcim.devices.filter(role=device_role)
  for dev in devices:
    config_file = f"{ config_dir }/{ inventory_hostname }.yml"
    struct_config = open_yaml_file(config_file)
    if struct_config == None:
        continue
    hash_init = hash_yaml_file(config_file)

    if device_role == 'standalone-media-switch':
        struct_config = process_switch(nb, struct_config, dev)
    elif device_role == 'ip-to-hdmi-gateway' or device_role == 'sdi-to-ip-gateway':
        struct_config = process_gateway(nb, struct_config, dev)
    else:
        continue

    write_yaml_file(config_file, struct_config, False)
    hash_end = hash_yaml_file(config_file)
    MODULE_LOGGER.info(f"{config_file}: HASH { hash_init } -> { hash_end }")
    has_changed = has_changed if hash_init == hash_end else True

  module.exit_json(changed=has_changed, msg=f"Received from NetBox, url= {module.params['nb_host']}")

if __name__ == "__main__":
  main()
