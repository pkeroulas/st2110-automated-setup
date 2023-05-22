#!/usr/bin/env python

import logging
import yaml, json
import os
import urllib.request
from ansible.module_utils.basic import AnsibleModule

MODULE_LOGGER = logging.getLogger('endpoint push config')
MODULE_LOGGER.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(message)s')
file_handler = logging.FileHandler('../roles/endpoints/gateways.log')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
MODULE_LOGGER.addHandler(file_handler)
MODULE_LOGGER.info('Start gateways module execution')

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

def get_from_url(url):
  req = urllib.request.Request(url)
  try:
    with urllib.request.urlopen(req) as response:
      return json.loads(response.read())
  except urllib.error.URLError as e:
    MODULE_LOGGER.error(f"{ e.reason }")
    return {}
  except Exception as e:
    MODULE_LOGGER.error(f"{ e.reason }")
    return {}

def main():
  module = AnsibleModule(
    argument_spec=dict(
      config_dir=dict(type='str', required=True),
      device_role=dict(type='str', required=True),
      inventory_hostname=dict(type='str', required=True),
    ),
    supports_check_mode=True,
  )
  config_dir  = module.params['config_dir']
  device_role  = module.params['device_role']
  inventory_hostname  = module.params['inventory_hostname']
  config_file = f"{ config_dir }/{ inventory_hostname }.yml"
  struct_config = open_yaml_file(config_file)
  MODULE_LOGGER.info(f" { config_file }: { struct_config }")

  url = f"http://{ struct_config['host_ip'] }/emsfp/node/v1/"
  res = get_from_url(url)
  MODULE_LOGGER.info(f"GET { req } >>> {} res }")

  # TODO: push
  has_changed = True

  module.exit_json(changed=has_changed, msg=f"Received from NetBox, url= {module.params['inventory_hostname']}")

if __name__ == "__main__":
  main()
