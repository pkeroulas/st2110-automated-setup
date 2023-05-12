#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright: (c) 2018, Société Radio-Canada>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
#

import logging
import yaml
import pynetbox
import hashlib
import re
import copy
from ansible.module_utils.basic import AnsibleModule

MODULE_LOGGER = logging.getLogger('get_netbox_data')
MODULE_LOGGER.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(message)s')
file_handler = logging.FileHandler('../inventories/switch/get_netbox_data.log')
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

STRUCTURE_PORT_TEMPLATE = {
  "description": "unused",
  "shutdown": False,
  "speed": "forced 25gfull",
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

def main():
  module = AnsibleModule(
    argument_spec=dict(
      nb_host=dict(type='str', required=True),
      token=dict(type='str', required=True),
      config_dir=dict(type='str', required=True),
    ),
    supports_check_mode=True,
  )
  nb_host = module.params['nb_host']
  token = module.params['token']
  config_dir  = module.params['config_dir']
  nb = pynetbox.api(nb_host,token)
  nb.http_session.verify = False

  devices = nb.dcim.devices.filter(role='standalone-media-switch')
  has_changed = False
  for dev in devices:
    MODULE_LOGGER.info(f"{ dev.name }")
    config_file = f"{ config_dir }/{ dev.name }.yml"
    structured_config = open_yaml_file(config_file)
    if structured_config == None:
        continue
    hash_init = hash_yaml_file(config_file)
    #MODULE_LOGGER.info(f"INIT {structured_config}")

    nb_ifaces = list(nb.dcim.interfaces.filter(device=dev.name))
    for nb_iface in nb_ifaces:
      if nb_iface.name == 'Ethernet48' or nb_iface.name == 'Management1': # Never touch the management link,
        continue

      # add missing
      if not nb_iface.name in structured_config['ethernet_interfaces']:
        structured_config['ethernet_interfaces'][nb_iface.name] = copy.deepcopy(STRUCTURE_PORT_TEMPLATE)

      structured_iface = structured_config['ethernet_interfaces'][nb_iface.name]
      structured_iface['description'] = nb_iface.description
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

    write_yaml_file(config_file, structured_config, False)
    hash_end = hash_yaml_file(config_file)
    #MODULE_LOGGER.info(f"END {structured_config}")
    MODULE_LOGGER.info(f"{config_file}: HASH { hash_init } -> { hash_end }")
    has_changed = has_changed if hash_init == hash_end else True

  module.exit_json(changed=has_changed, msg=f"Received from NetBox, url= {module.params['nb_host']}")

if __name__ == "__main__":
  main()
