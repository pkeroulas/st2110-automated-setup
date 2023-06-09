#!/usr/bin/env python

import logging
import yaml, json
import os
import hashlib
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


def get_dict_hash(data):
  hash_md5 = hashlib.md5()
  hash_md5.update(json.dumps(data, sort_keys=True).encode('utf-8'))
  hash_md5.hexdigest()

def open_yaml_file(filename):
  if not os.path.isfile(filename):
    yaml_dict = {}
    write_yaml_file(filename, yaml_dict, sort=True)
    return yaml_dict

  with open(filename, 'r') as stream:
    try:
      return yaml.safe_load(stream)
    except yaml.YAMLError as exc:
      MODULE_LOGGER.info(exc)
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

def put_to_url(url, data):
  try:
    req = urllib.request.Request(url, json.dumps(data).encode('utf-8'), {'Content-Type':'application/json'})
    req.get_method = lambda: 'PUT'
    with urllib.request.urlopen(req) as response:
      return json.loads(response.read())
  except urllib.error.URLError as e:
    MODULE_LOGGER.error(f"{ e.reason }")
    return {}
  except Exception as e:
    MODULE_LOGGER.error(f"{ e }")
    return {}

def process_audio_map(url, struct_audio_map):
  api_sdi_ids = get_from_url(f"{ url }/sdi_audio/")
  MODULE_LOGGER.info(f"API GET { url } >>> { api_sdi_ids }")
  if len(api_sdi_ids) != 2:
    MODULE_LOGGER.info(f"API Couldn't get SDI ids from { url }")
    module.exit_json(changed=has_changed, msg=f"Failed")

  api_sdi_audio = get_from_url(f"{ url }/sdi_audio/{ api_sdi_ids[0] }") # 1st sdi only
  hash_init = get_dict_hash(api_sdi_audio)

  for struct_sdi in struct_audio_map.keys():
    struct_sdi_i = struct_sdi.replace('sdi','') # index
    struct_ip_i = struct_audio_map[struct_sdi].replace('ip','')
    if not struct_sdi_i.isdigit() or not struct_ip_i.isdigit():
      MODULE_LOGGER.info(f"Struct conf is malformed { struct_audio_map }")

    struct_sdi_i = str(int(struct_sdi_i)-1) # start from 0
    if not f'ch{struct_sdi_i}' in api_sdi_audio['sdi_aud_chans_cfg']:
      MODULE_LOGGER.info(f"API conf {api_sdi_audio['sdi_aud_chans_cfg']} doesn\'t contain ch{ struct_sdi_i }")

    api_sdi = api_sdi_audio['sdi_aud_chans_cfg'][f'ch{ struct_sdi_i }']
    api_sdi_l = api_sdi.split(':')
    if len(api_sdi_l) != 3:
      MODULE_LOGGER.info(f"API ch{ struct_sdi_i } is malformed { api_sdi }")

    api_sdi_l[1] = str(int(struct_ip_i)-1) # start from 0
    api_sdi_l[2] = '1' # enable
    api_sdi=':'.join(api_sdi_l)

    api_sdi_audio['sdi_aud_chans_cfg'][f'ch{ struct_sdi_i }'] = api_sdi

  hash_end = get_dict_hash(api_sdi_audio)

  MODULE_LOGGER.info(f"API PUT audio { api_sdi_audio }")
  ret = put_to_url(f"{ url }/sdi_audio/{ api_sdi_ids[0] }", api_sdi_audio) # 1st sdi only
  MODULE_LOGGER.info(f"API GET audio { ret }")

  return hash_init != hash_end

def main():
  module = AnsibleModule(
    argument_spec=dict(
      config_dir=dict(type='str', required=True),
    ),
    supports_check_mode=True,
  )
  config_dir  = module.params['config_dir']
  config_file = f"{ config_dir }/hosts.yml"
  struct_config = open_yaml_file(config_file)
  MODULE_LOGGER.info(f" { config_file }: { struct_config }")
  hosts = struct_config['all']['children']['DC']['hosts']

  for host in hosts.keys():
    struct_config_dev = hosts[host]
    struct_audio_map = struct_config_dev['config_context']['audio_map']

    has_changed = False
    if struct_config_dev['status'] != 'active':
        continue

    if struct_config_dev['device_role'] == 'ip-to-sdi-gateway':
      url = f"http://{ struct_config_dev['host_ip'] }/emsfp/node/v1/"
      has_changed = process_audio_map(url, struct_audio_map)

  module.exit_json(changed=has_changed, msg=f"Pushed config")

if __name__ == "__main__":
  main()
