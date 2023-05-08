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
from ansible.module_utils.basic import AnsibleModule

MODULE_LOGGER = logging.getLogger('get_netbox_data')
MODULE_LOGGER.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(message)s')
file_handler = logging.FileHandler('../inventories/switch/get_netbox_data.log')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
MODULE_LOGGER.addHandler(file_handler)
MODULE_LOGGER.info('Start get_netbox_data module execution')

def write_yaml_file(filename, yaml_dict, sort=True):
  with open(filename, 'w') as f:
    yaml.dump(yaml_dict, f,default_flow_style=False,indent=2,sort_keys=sort)

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

def main():
  module = AnsibleModule(
    argument_spec=dict(
      nb_host=dict(type='str', required=True),
      token=dict(type='str', required=True),
      config_file=dict(type='str', required=True),
    ),
    supports_check_mode=True,
  )
  nb_host = module.params['nb_host']
  token = module.params['token']
  config_file  = module.params['config_file']

  nb = pynetbox.api(nb_host,token)
  nb.http_session.verify = False

  structured_config = open_yaml_file(config_file)
  hash_init = hash_yaml_file(config_file)

  devices=nb.dcim.devices.filter(role='standalone-media-switch')
  fmt = "{:<20}{:<20}{:<30}{:<60}"
  header = ("Name", "Device Role", "Description", "Config Context")
  MODULE_LOGGER.info(fmt.format(*header))
  for dev in devices:
    MODULE_LOGGER.info(f"{ dev.name }")
    ifaces = list(nb.dcim.interfaces.filter(device=dev.name))
    for iface in ifaces:
      if iface.name in structured_config['ethernet_interfaces']:
        MODULE_LOGGER.info(f"{ iface.name } FOUND ")
    else:
        MODULE_LOGGER.info(f"{ iface.name } NOT FOUND ")

  write_yaml_file(config_file, structured_config, False)
  hash_end = hash_yaml_file(config_file)
  #MODULE_LOGGER.info(f"HASH { hash_init } { hash_end }")

  changed = False if hash_init == hash_end else True
  module.exit_json(changed=changed, msg=f"Received from NetBox, url= {module.params['nb_host']}")

if __name__ == "__main__":
  main()
