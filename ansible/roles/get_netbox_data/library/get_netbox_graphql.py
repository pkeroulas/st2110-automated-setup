#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright: (c) 2018, Société Radio-Canada>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
#

import logging
import yaml
import netaddr
import pynetbox
import hashlib
import re
import requests
import time
import copy
from ansible.module_utils.basic import AnsibleModule

MODULE_LOGGER = logging.getLogger('get_netbox_data')
MODULE_LOGGER.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(message)s')

file_handler = logging.FileHandler('../inventories/switch/get_netbox_graphql.log')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

MODULE_LOGGER.addHandler(file_handler)
MODULE_LOGGER.info('Start get_netbox_data module execution')

RedSwitchRegEx = r'MPR|PRR|mpr|prr'
BlueSwitchRegEx = r'MPB|PRB|mpb|prb'
PurpleSwitchRegEx = r'MPX|PRX|mpx|prx'

POD_DIGITS = 3

CVP_DEFAULTS={ 'ansible_connection': 'httpapi',
          'ansible_host': '192.168.0.0',
          'ansible_httpapi_host': '192.168.0.0',
          'ansible_httpapi_port': int('443'),
          'ansible_httpapi_use_ssl': bool(True),
          'ansible_httpapi_validate_certs': bool(False),
          'ansible_network_os': 'eos',
          'ansible_password': '''{{ vault_arista_pass2 }}''',
          'ansible_python_interpreter': '/usr/bin/env python',
          'ansible_user': '''{{ vault_arista_user2 }}''' }

INIT_RT_CONNECTIONS = { 'ethernet_interfaces' : {} ,
    'management_interfaces':{} ,
    'router_bgp_neighbors': {} }

DEFAULT_PIM = {'ipv4': {'sparse_mode': bool(True) }}
DEFAULT_MC  = {'ipv4': {'static': bool(True) }}
DEFAULT_PTP = { 'enable': bool(True),
                'announce': {'interval': 0},
                'delay_req': -3,
                'sync_message': { 'interval': -3},
                'role': 'master'}
UPLINK_PTP = { 'enable': bool(True),
                'announce': {'interval': 0},
                'delay_req': -3,
                'sync_message': { 'interval': -3}}
DEFAULT_LOAD_INTERVAL = 5

DEFAULT_CONNECTIONS = {'uplink_interface_speed': 'forced 10000full',
  'uplink_interfaces': ['Ethernet49','Ethernet50'],
  'mlag_interfaces': ['Ethernet51','Ethernet52'],
  'p2p_ip_addresses' : [],
  'nodes' : {1 : {'uplink_switch_interfaces': ['Ethernet1','Ethernet1'], 'p2p_ips': ['',''], 'dci' : { 'interface' : [], 'p2p': [], 'device':[], 'p2p_ips' : [], 'int_speed' : [] } },
             2 : {'uplink_switch_interfaces': ['Ethernet2','Ethernet2'], 'p2p_ips': ['',''], 'dci' : { 'interface' : [], 'p2p': [], 'device':[], 'p2p_ips' : [], 'int_speed' : [] } } }}

DEFAULT_L2_DATA = {'mlag_interfaces':[],
                    'uplink_interface':[],
                    'uplink_interface_speed': 'forced 10000full',
                    'connnected_endpoints':[],
                    'connected_interfaces':[]}

ABREVIATED_CITY ={'montreal': 'MTL',
                  'toronto' : 'TOR',
                  'vancouver' : 'VCR',
                  'ottawa' : 'OTT',
                  'sydney' : 'SYD',
                  'st-johns' : 'SNF',
                  'yellowknife' : 'YKN' }

def write_yaml_file(filename, yaml_dict, sort=True):
  with open(filename, 'w') as f:
    yaml.dump(yaml_dict, f,default_flow_style=False,indent=2,sort_keys=sort)

def get_title(desc):
  return desc[desc.find("[")+1:desc.find("]")]

def get_fabric_config_contexts(nb,city,network):
  cc = {}
  config_contexts = nb.extras.config_contexts.filter(site=city,tag=network)
  MODULE_LOGGER.error(f"adding EXTRAS / config_consxt of {city}- {network} -{config_contexts} ")
  for c in config_contexts: cc.update( { get_title(c.description) : {} }  )
  for c in config_contexts: cc[ get_title(c.description)].update( {c.roles[0].slug : {} })
  for c in config_contexts: cc[ get_title(c.description)][ c.roles[0].slug ].update( c.data )

  return cc

def get_connections(nb,sw_name,b_sw_name):
  mlag = []
  device_p2p = []
  spine_p2p = []
  spine_p2p_ips = []
  l2_data = DEFAULT_L2_DATA
  int_speed = 'forced 10000full'
  dci = { 'interface' : [], 'p2p': [], 'device':[], 'p2p_ips' : [], 'int_speed' : []}
  sw_name = sw_name.upper()
  b_sw_name = b_sw_name.upper()
  device_connections = copy.deepcopy(DEFAULT_CONNECTIONS)

  if 'SW' in sw_name:
    l2_data = get_l3_information(nb,sw_name,b_sw_name)
    mlag = l2_data['mlag_interfaces']
    device_p2p = l2_data['uplink_interface']
    int_speed = l2_data['uplink_interface_speed']
  else:
    intfs = nb.dcim.interfaces.filter(device=sw_name)
    for i in intfs:
      if i.tags :
        tag_list = get_tags_list(i)
        if 'nw_mlag' in tag_list:
          mlag.append(i.name)
          try:
            MODULE_LOGGER.info(f"Connections ~~~~ {i}---{i.connected_endpoints[0]} -- {i.connected_endpoints[0].device} --- {i.type.value.split('base')[0]}")
          except Exception as e:
            MODULE_LOGGER.error(f" {sw_name}/{i.name} has no MLAG connections [{e}] ")

        if 'nw_p2p' in tag_list:
          intf_address = get_interface_address(i.name,sw_name,nb)
          if not intf_address: MODULE_LOGGER.error(f"{sw_name}|{i.name}| is missing P2P_ip")
          if 'SP' not in sw_name:
            device_p2p.append(i.name)
            spine_p2p.append(i.connected_endpoints[0].name)
            spine_p2p_ips.append(intf_address)
          int_speed = format_speed(i.type.value.split('base')[0],i.name+sw_name+b_sw_name)

        if 'nw_dci' in tag_list:
          intf_address = get_interface_address(i.name,sw_name,nb)
          if not intf_address: MODULE_LOGGER.error(f"{sw_name}|{i.name}| is missing P2P_ip")
          dci['interface'].append(i.name)
          dci['p2p'].append(i.connected_endpoints[0].name)
          dci['device'].append(i.connected_endpoints[0].device.name)
          dci['p2p_ips'].append(intf_address)
          dci['int_speed'].append(format_speed(i.type.value.split('base')[0],i.name+sw_name+b_sw_name))

  MODULE_LOGGER.info(f"SPINE Interfaces for ~~~{sw_name} -- {b_sw_name} ==  {spine_p2p}")
  device_connections['uplink_interface_speed'] = int_speed
  device_connections['mlag_interfaces'] = mlag
  device_connections['uplink_interfaces'] = device_p2p
  device_connections['nodes'][1]['uplink_switch_interfaces'] = spine_p2p
  device_connections['nodes'][1]['p2p_ips'] = spine_p2p_ips
  device_connections['parent_l3leafs'] = l2_data['connnected_endpoints']
  device_connections['l3leaf_interfaces'] = l2_data['connected_interfaces']

  if dci['interface']:
    device_connections['nodes'][1]['dci']['interface'] = dci['interface']
    device_connections['nodes'][1]['dci']['device'] = dci['device']
    device_connections['nodes'][1]['dci']['p2p'] = dci['p2p']
    device_connections['nodes'][1]['dci']['p2p_ips'] = dci['p2p_ips']
    device_connections['nodes'][1]['dci']['int_speed'] = dci['int_speed']
    MODULE_LOGGER.info(f"DCI info |{sw_name}| -- {dci['interface']} -- {dci['p2p']} -- {dci['p2p_ips']} [{device_connections}] ")

  spine_p2p = []
  spine_p2p_ips = []
  intfs = nb.dcim.interfaces.filter(device=b_sw_name,tag='nw_p2p')
  for i in intfs:
    intf_address = get_interface_address(i.name,b_sw_name,nb)
    if not intf_address: MODULE_LOGGER.error(f"{b_sw_name}|{i.name}| is missing P2P_ip")
    try:
      spine_p2p.append(i.connected_endpoints[0].name)
      spine_p2p_ips.append(intf_address)
    except:
      MODULE_LOGGER.error(f"Missing NetBox connected endpoint {b_sw_name} --| {i} |")
  if 'SP' in b_sw_name:
    device_connections['nodes'][2]['uplink_switch_interfaces'] = []
    device_connections['nodes'][2]['p2p_ips'] = []
  else:
    device_connections['nodes'][2]['uplink_switch_interfaces'] = spine_p2p
    device_connections['nodes'][2]['p2p_ips'] = spine_p2p_ips

  intfs = nb.dcim.interfaces.filter(device=b_sw_name,tag='nw_dci')
  for i in intfs:
    intf_address = get_interface_address(i.name,b_sw_name,nb)
    if not intf_address: MODULE_LOGGER.error(f"{b_sw_name}|{i.name}| is missing P2P_ip")
    device_connections['nodes'][2]['dci']['interface'].append(i.name)
    device_connections['nodes'][2]['dci']['device'].append(i.connected_endpoints[0].device.name)
    device_connections['nodes'][2]['dci']['p2p'].append(i.connected_endpoints[0].name)
    device_connections['nodes'][2]['dci']['p2p_ips'].append(intf_address)
    device_connections['nodes'][2]['dci']['int_speed'].append(format_speed(i.type.value.split('base')[0],i.name+sw_name+b_sw_name))
    MODULE_LOGGER.info(f"DCI info BW == |{sw_name}|{i} -- [{device_connections}] ")
  MODULE_LOGGER.error(f"DEBUG DCI == |{sw_name}| -- {intfs} -- |{device_connections['nodes'][2]['dci']}|  ")
  return device_connections

def get_l3_information(nb,sw_name,b_sw_name):
  single = []
  single_devices = []
  l2_device_data = DEFAULT_L2_DATA
  l3_connection_interface = nb.dcim.interfaces.filter(device=sw_name,tag='nw_l2leafs')
  l3_connection_interface_name = get_interface_name(l3_connection_interface)
  mlag_interfaces = get_interface_name(nb.dcim.interfaces.filter(device=sw_name,tag='nw_mlag'))
  MODULE_LOGGER.info(f" L3 interfaces = {l3_connection_interface_name}  MLAG -int = {mlag_interfaces}")
  try:
    if 'SINGLE' in b_sw_name:
      for lag in l3_connection_interface_name:
        loop_index = 0
        single.append( nb.dcim.interfaces.get(device=sw_name,name=lag) )
        single_devices.append(single[loop_index].connected_endpoints[0].device.name)
        loop_index += 1
    else:
      first = nb.dcim.interfaces.get(device=sw_name,name=l3_connection_interface_name)
      first_connected_device = first.connected_endpoints[0].device.name
      second = nb.dcim.interfaces.get(device=b_sw_name,name=l3_connection_interface_name)
      second_connected_device = second.connected_endpoints[0].device.name
  except Exception as e:
    MODULE_LOGGER.error(f"Missing NetBox L2LEAF connection ~~~ {sw_name} -{b_sw_name} ~~~ |{e}|")
    return DEFAULT_L2_DATA

  MODULE_LOGGER.info(f" L2 int speed  {sw_name} = {l3_connection_interface_name} | {l3_connection_interface[0].type.value.split('base')[0] } |")
  if 'SINGLE' in b_sw_name:
    l2_device_data['uplink_interface_speed'] = format_speed(l3_connection_interface[0].type.value.split('base')[0],l3_connection_interface[0].name+sw_name+b_sw_name)
    l2_device_data['mlag_interfaces'] = mlag_interfaces
    l2_device_data['uplink_interface'] = l3_connection_interface_name
    l2_device_data['connnected_endpoints'] = [single[0].connected_endpoints[0].device.name , single[1].connected_endpoints[0].device.name ]
    l2_device_data['connected_interfaces'] = [single[0].connected_endpoints[0].name , single[1].connected_endpoints[0].name ]
  else:
    l2_device_data['uplink_interface_speed'] = format_speed(l3_connection_interface[0].type.value.split('base')[0],l3_connection_interface[0].name+sw_name+b_sw_name)
    l2_device_data['mlag_interfaces'] = mlag_interfaces
    l2_device_data['uplink_interface'] = l3_connection_interface_name
    l2_device_data['connnected_endpoints'] = [first_connected_device,second_connected_device ]
    l2_device_data['connected_interfaces'] = [first.connected_endpoints[0].name,second.connected_endpoints[0].name]
  return l2_device_data

def get_interface_name(intfs):
  intf_list = []
  for intf in intfs:
    intf_list.append(intf.name)
  return intf_list

def get_tags_list(intf):
  tag_list = []
  for tag in intf.tags:
    tag_list.append(tag.name)
  return tag_list

def get_fabric_pod(nb,sw,b_sw):
  fabric_dict ={}
  sw_name= sw.name.upper()
  b_sw_name = b_sw.name.upper() if b_sw else 'single-000'

  conn_details = get_connections(nb,sw_name,b_sw_name)
  MODULE_LOGGER.info(f"Connection Details {sw_name} -- {conn_details} ")
  # prf = ABREVIATED_CITY[city]+'_'+system.upper()+'_'
  prf = ''
  if 'blf' in sw_name.lower():
    pod = prf + 'BLF' + sw_name[-POD_DIGITS:] + b_sw_name[-POD_DIGITS:]
  elif 'dlf' in sw_name.lower():
    pod = prf + 'DLF' + sw_name[-POD_DIGITS:] + b_sw_name[-POD_DIGITS:]
  elif 'sw' in sw_name.lower():
    pod = prf + 'SW' + sw_name[-POD_DIGITS:] + b_sw_name[-POD_DIGITS:]
  elif 'sp' in sw_name.lower():
    pod = prf+'SPINES'
  else:
    pod = 'invalid'
  if sw.custom_fields['bgp_asn']:
    bgp = int(sw.custom_fields['bgp_asn'])
  else:
    bgp= 0
    MODULE_LOGGER.error(f"{sw_name} Does not have BGP ASN. Using BGP_ASN=0")

  if b_sw:
    fabric_dict = get_double_fabric(pod,sw,b_sw,conn_details,bgp)
  else:
    fabric_dict = get_single_fabric(pod,sw,b_sw,conn_details,bgp)


  return fabric_dict
    # device_connections['nodes'][2]['dci']['interface'] = i.name
    # device_connections['nodes'][2]['dci']['p2p'] = i.connected_endpoints[0].name
    # device_connections['nodes'][2]['dci']['p2p_ips'] = intf_address
    # device_connections['nodes'][2]['dci']['int_speed']
def get_double_fabric(pod,sw,b_sw,conn_details,bgp):
  sw_tag,b_sw_tag = get_nw_service_tags(sw,b_sw)
  fabric_dict = { pod : { 'bgp_asn' : bgp,
                          'platform' : sw.device_type.model,
                          'uplink_interface_speed' : conn_details['uplink_interface_speed'],
                          'uplink_interfaces' : conn_details['uplink_interfaces'],
                          'mlag_interfaces' : conn_details['mlag_interfaces'],
                          'filter' : { 'tags' : sw_tag },
                         'nodes' : { sw.name : { 'mgmt_ip': sw.primary_ip4.address, 'avd_id': sw.custom_fields['avd_id'],
                         'uplink_switch_interfaces': conn_details['nodes'][1]['uplink_switch_interfaces'] ,
                         'p2p_ips': conn_details['nodes'][1]['p2p_ips'] },
                         b_sw.name :  {'mgmt_ip': b_sw.primary_ip4.address, 'avd_id': b_sw.custom_fields['avd_id'],
                         'uplink_switch_interfaces': conn_details['nodes'][2]['uplink_switch_interfaces'],
                         'p2p_ips': conn_details['nodes'][2]['p2p_ips']  }} } }

  if conn_details['nodes'][1]['dci']['device'] != []:
    MODULE_LOGGER.error(f"SHOULD NOT HAVE THIS |{sw.name}| == {conn_details['nodes'][1]['dci']}")
    fabric_dict[pod]['nodes'][sw.name].update({'dci' : conn_details['nodes'][1]['dci'] })
    fabric_dict[pod]['nodes'][b_sw.name].update({'dci' : conn_details['nodes'][2]['dci'] })

  if 'sw' in sw.name.lower():
    fabric_dict[pod].update({ 'uplink_switches':conn_details['parent_l3leafs']})
    fabric_dict[pod]['nodes'][sw.name].update({ 'uplink_switch_interfaces' : [conn_details['l3leaf_interfaces'][0]]  })
    fabric_dict[pod]['nodes'][b_sw.name].update({ 'uplink_switch_interfaces' : [conn_details['l3leaf_interfaces'][1]] })
  return fabric_dict

def get_single_fabric(pod,sw,b_sw,conn_details,bgp):
  sw_tag,b_sw_tag = get_nw_service_tags(sw,b_sw)
  fabric_dict = { pod : { 'bgp_asn' : bgp,
                          'platform' : sw.device_type.model,
                          'uplink_interface_speed' : conn_details['uplink_interface_speed'],
                          'uplink_interfaces' : conn_details['uplink_interfaces'],
                          'mlag_interfaces' : conn_details['mlag_interfaces'],
                          'filter' : { 'tags' : sw_tag },
                         'nodes' : { sw.name : { 'mgmt_ip': sw.primary_ip4.address, 'avd_id': sw.custom_fields['avd_id'],
                         'uplink_switch_interfaces': conn_details['nodes'][1]['uplink_switch_interfaces'] }} } }
  if 'sw' in sw.name.lower():
    fabric_dict[pod].update({ 'uplink_switches': conn_details['parent_l3leafs']})
    fabric_dict[pod]['nodes'][sw.name].update({ 'uplink_switch_interfaces' : conn_details['l3leaf_interfaces']  })

  MODULE_LOGGER.warning(f"{fabric_dict}")
  return fabric_dict

def get_nw_service_tags(a,b):
  if b:
    a_tag = a.custom_fields['networkservicetags'].split(',') if a.custom_fields['networkservicetags'] else []
    b_tag = b.custom_fields['networkservicetags'].split(',') if b.custom_fields['networkservicetags'] else []
    return a_tag, b_tag
  else:
    a_tag = a.custom_fields['networkservicetags'].split(',') if a.custom_fields['networkservicetags'] else []
    return a_tag, None

def get_double_pod(sw,b_sw,dev_type):
  try:
    primary_sw = netaddr.IPNetwork(sw.primary_ip4.address)
    backup_sw = netaddr.IPNetwork(b_sw.primary_ip4.address)
    net_tag,b_net_tag = get_nw_service_tags(sw,b_sw)
    pod_dict = {'hosts': {sw.name : { 'ansible_host': str(primary_sw.ip),
                               'type' : dev_type ,
                               'device_platform': sw.device_type.model,
                               'avd_id' : sw.custom_fields['avd_id'],
                              #  'location': sw.rack.name,
                               'status' : sw.status.value ,
                               'networkservicetags' :  net_tag },
                               b_sw.name :  {'ansible_host': str(backup_sw.ip) ,
                               'type' : dev_type ,
                               'device_platform': b_sw.device_type.model,
                               'avd_id' : b_sw.custom_fields['avd_id'],
                              #  'location': b_sw.rack.name,
                               'status' : b_sw.status.value ,
                               'networkservicetags' :  b_net_tag  }} }
  except Exception as e:
    MODULE_LOGGER.error(f"CTRL: pod | {sw.name} | is missing informationin NetBox -- EXCEPTION={e}")
    return None
  return pod_dict

def get_single_pod(sw,dev_type):
  try:
    primary_sw = netaddr.IPNetwork(sw.primary_ip4.address)
    net_tag,b_net_tag = get_nw_service_tags(sw,'')
    pod_dict = {'hosts': {sw.name : { 'ansible_host': str(primary_sw.ip),
                               'type' : dev_type ,
                               'device_platform': sw.device_type.model,
                               'avd_id' : sw.custom_fields['avd_id'],
                              #  'location': sw.rack.name,
                               'status' : sw.status.value ,
                               'networkservicetags' :  net_tag },} }
  except Exception as e:
    MODULE_LOGGER.error(f"CTRL: pod | {sw.name} | is missing informationin NetBox -- EXCEPTION={e}")
    return None
  return pod_dict

def get_pod_name(sw,b_sw,city,system):
  pod_dict ={}
  sw_name= sw.name.upper()
  b_sw_name = b_sw.name.upper() if b_sw else 'single-000'
  # if city == 'montreal':
  #   sw_name= sw.name.lower()
  #   b_sw_name = b_sw.name.lower()
  # else:
  #   sw_name= sw.name.upper()
  #   b_sw_name = b_sw.name.upper()

  prf = ABREVIATED_CITY[city]+'_'+system.upper()+'_'
  if 'blf' in sw_name.lower():
    pod = prf + 'BLF' + sw_name[-POD_DIGITS:] + b_sw_name[-POD_DIGITS:]
    dev_type = 'l3leaf'
  elif 'dlf' in sw_name.lower():
    pod = prf + 'DLF' + sw_name[-POD_DIGITS:] + b_sw_name[-POD_DIGITS:]
    dev_type = 'l3leaf'
  elif 'sw' in sw_name.lower():
    pod = prf + 'SW' + sw_name[-POD_DIGITS:] + b_sw_name[-POD_DIGITS:]
    dev_type = 'l2leaf'
  elif 'sp' in sw_name.lower():
    pod = prf+'SPINES'
    dev_type = 'spine'
  else:
    pod = 'invalid'

  if b_sw:
    pod_dict = get_double_pod(sw,b_sw,dev_type)
  else:
    pod_dict = get_single_pod(sw,dev_type)

  return pod,pod_dict

def get_ptp_port(sw_name,intf,peer,pt,spd):
  cfg = {}
  cfg.update({ intf.name : {
      'description' :  'p2p_link_to_' + peer + '_' + pt + ' [PTP]',
      'shutdown' : not bool('true') ,
      'speed' : format_speed(spd,sw_name+peer+pt),
      'type' : 'routed',
      'ptp' : UPLINK_PTP ,
        } })
  return cfg

def get_interface_address(intf,sw_name,nb):
  try:
    # MODULE_LOGGER.info(f" Getting ip for {sw_name} |{intf}| ")
    ip = nb.ipam.ip_addresses.get(device=sw_name,interface=intf)
    valid_ip = netaddr.IPNetwork(ip.address)
  except Exception as e:
    MODULE_LOGGER.error(f" {sw_name} |{intf}| is missing a valid p2p IP address EXCEPTION={e} ")
    return
  return str(valid_ip)

def get_p2p_port(sw_name,intf,peer,pt,spd,nb):
  cfg = {}
  interface_address = get_interface_address(intf.name,sw_name,nb)
  if not interface_address:
    MODULE_LOGGER.error(f"MISSING IP-Address = {sw_name}|{intf.name}| ")
    return
  cfg.update({ intf.name : {
      'description' :  'p2p_link_to_' + peer + '_' + pt,
      'ip_address' : interface_address,
      'shutdown' : not bool('true') ,
      'speed' : format_speed(spd,sw_name+peer+pt),
      'type' : 'routed',
      'pim': DEFAULT_PIM,
      'ptp' : UPLINK_PTP ,
        } })
  if 'mtl' in sw_name.lower():
    cfg[intf.name].update({'multicast' : DEFAULT_MC })
  return cfg

def find_neighbour_address(ipa,sw,pt):
  if ipa.split("/")[1] == "31":
    valid_ip = netaddr.IPNetwork(ipa)
    other_address = [x for x in list(valid_ip) if x != valid_ip.ip]
    return f"{str(other_address[0])}/31"
  else:
    MODULE_LOGGER.error(f"INVALID p2p IP Address {ipa} in {sw}|{pt}|")
    return ""

def write_inventory(gql,nb,system,suffix,locations):
  roles = []
  lab_devs = []
  folder = locations[suffix] + '/'
  network = system + '_' + suffix
  MODULE_LOGGER.info(f"--------------{network}")
  city = folder.split('/')[2]
  network=network.upper()
  city_net = ABREVIATED_CITY[city]+'_'+network
  lab_devices = nb.dcim.devices.filter(site=city,tag=network.lower())

  save_start = time.time()
  for lab_dev_name in lab_devices:
    MODULE_LOGGER.info(f"getting data for {lab_dev_name} - {type(lab_dev_name)} -- {type(lab_dev_name.name)}")
    lab_dev = nb.dcim.devices.get(name=lab_dev_name.name)
    roles.append( lab_dev.device_role.slug.upper()+ '_' + city_net.upper() )
    lab_devs.append(lab_dev)
  roles = set(roles)
  MODULE_LOGGER.error(f"FABRIC ROLES = {roles}")
  MODULE_LOGGER.warning(f"Saving switch objects takes = {time.time() - save_start} seconds")

  if suffix == 'ctrl':
    save_ctrl_vars(nb,lab_devs,locations,city,system)
  elif suffix == 'rt':
    save_rt_vars(gql,nb,lab_devs,locations,city,network)

def save_rt_vars(gql,nb,lab_devs,locations,city,network):
  rt_fabric = { 'leaf_red' : {} ,'leaf_blue' : {},'leaf_purple' : {},
                'spine_blue' : {},'spine_red' : {} , 'config_contexts' : {} , 'rt_device_data' : {}, 'device_config_context': {} }
  number_of_switches = len(lab_devs)
  i = 1
  for sw in lab_devs:
    start = time.time()
    rt = get_rt_fabric(gql,sw)
    rt_fabric[rt['type']].update({ sw.name : rt })

    rt_fabric['rt_device_data'].update( format_device_data(sw) )
    if sw.config_context: rt_fabric['device_config_context'].update( { sw.name : sw.config_context })

    end = time.time()
    MODULE_LOGGER.warning(f" Duration for {i}/{number_of_switches} {sw.name} ===== {end - start} ")
    i +=1

  rt_fabric['config_contexts'].update( get_fabric_config_contexts( nb,city,network.lower() ) )

  write_yaml_file(locations['vars']+'/nb_rt_fabric.yml',rt_fabric)

def format_device_data(sw):
  dd = {sw.name : { 'ansible_host': str(sw.primary_ip4.address),
                      'device_platform': sw.device_type.model,
                      'status' : sw.status.value ,
                      'config_context' : sw.config_context  }}
  MODULE_LOGGER.info(f"Device data {dd} ")
  return dd

def save_ctrl_vars(nb,lab_devs,locations,city,system):
  pods = []
  pod_d = {}
  fabric = {'l2leafs' : {} ,'l3leafs' : {} , 'spines' : {},'device_data' : {} }
  for sw in lab_devs:
    switch = sw.name
    switch_number = int(switch[-3:])
    if (switch_number % 2 ) !=0 : # Start with ODD switches
      backup_switch_number = switch_number + 1
      backup_switch_intstr = str(backup_switch_number).rjust(3,"0")
      #MODULE_LOGGER.info(f"******{switch}--{lab_devs}---{backup_switch_intstr}**********")
      try:
        backup_sw = [s for s in lab_devs if backup_switch_intstr in s.name][0]
      except Exception as e:
        if 'sw' in switch.lower():
          MODULE_LOGGER.warning(f"Single L2Leaf configuration for |{switch}|")
          backup_sw = ''
        else:
          MODULE_LOGGER.error(f"No backap switch for {switch} is present in NetBox |{e}|")
          raise SystemExit
      pod,pd = get_pod_name(sw,backup_sw,city,system)
      if not pd: continue
      pod_d.update({pod : {}})
      pod_d[pod].update(pd)
      pods.append(pod)
      f_pod = get_fabric_pod(nb,sw,backup_sw)
      MODULE_LOGGER.error(f' == f_pod = {f_pod.keys()} ')
      if 'sp' in switch.lower():
        fabric['spines'].update(f_pod['SPINES'])
      elif 'sw' in switch.lower():
        fabric['l2leafs'].update(f_pod)
      else:
        fabric['l3leafs'].update(f_pod)
      fabric['device_data'].update(pd['hosts'])
  MODULE_LOGGER.info(f"POD- Name = {pod_d.keys()} ")

  MODULE_LOGGER.error(f"{fabric['l3leafs'].keys()}")
  write_yaml_file(locations['vars']+'/nb_fabric.yml',fabric)

def get_connected_endpoints(interface):
  peer = interface.connected_endpoints[0].device.name
  peer_port = interface.connected_endpoints[0].name
  speed = 'forced ' + interface.type.value.split('base')[0]+'full'
  return peer, peer_port,speed

def combine_et_data( a,b,c={} ):
  return  {**a,**b,**c}

def format_custom_fields(c_field):
  if c_field['bgp_asn']:
    bgp = int(c_field['bgp_asn'])
  else:
    bgp= 0
  if c_field['networkservicetags']:
    network_services = [c_field['networkservicetags']]
  else:
    network_services= ['']
  return bgp,network_services

def get_tags_list(intf):
  tag_list = []
  for tag in intf.tags:
    tag_list.append(tag.name)
  return tag_list

def get_p2p_port_gql(sw_name,intf,peer,pt,spd):
  cfg = {}
  try:
    if not intf["ip_addresses"][0]["address"]:
      MODULE_LOGGER.info(f"MISSING IP-Address = {sw_name}|{intf['name']}| ")
      return
  except IndexError:
      MODULE_LOGGER.info(f"MISSING IP-Address = {sw_name}|{intf['name']}| ")
      return

  cfg.update({ intf["name"] : {
      'description' :  'p2p_link_to_' + peer + '_' + pt,
      'ip_address' : intf["ip_addresses"][0]["address"],
      'shutdown' : not bool('true') ,
      'speed' : format_speed(spd,sw_name+peer+pt),
      'type' : 'routed',
      'pim': DEFAULT_PIM,
      'ptp' : UPLINK_PTP ,
        } })
  return cfg

def get_ptp_port(sw_name,intf,peer,pt,spd):
  cfg = {}
  cfg.update({intf["name"] : {
      'description' :  'p2p_link_to_' + peer + '_' + pt + ' [PTP]',
      'shutdown' : not bool('true') ,
      'speed' : format_speed(spd,sw_name+peer+pt),
      'type' : 'routed',
      'ptp' : UPLINK_PTP ,
        } })
  return cfg

def get_connected_endpoints_gql(interface):
  try:
    peer = interface["connected_endpoint"]["name"]
    peer_port = interface["connected_endpoint"]["interface"]
    speed = interface["type"]
  except:
    MODULE_LOGGER.info(f"MISSSING connected endpoint !!!!!!!------{interface}")
    return '','',''
  return peer, peer_port,speed

def format_speed(sp,description):
  sp = sp.lower()
  speed ='auto'
  if '25g' in sp:
    speed = 'forced 25gfull'
  elif '10g' in sp:
    speed = 'forced 10000full'
  elif '40g' in sp:
    speed = 'forced 40gfull'
  elif '100g' in sp:
    speed = 'forced 100gfull'
  elif '1g' in sp:
    speed = 'forced 1000full'
  elif '1000' in sp:
    speed = 'forced 1000full'
  else:
    ## TODO Learn how to raise an exception in Ansible and stop
    MODULE_LOGGER.error('Formating speed {}-{}'.format(sp,description))
  return speed

def filter_interface_tags( interfaces ):
  intfs = { "nw_p2p" : [], "nw_ptp" : [], "nw_l3edge" : [], "nw_tieline" : [] }
  for i in interfaces:
    for k in intfs:
      if k in i["tags"]:
        intfs[k].append( i )
  return intfs

def format_p2p_data(interfaces,sw_name):
  p2p_data = {  'intfs':[], 'ips' :[], 'peer':[],'peer_intfs':[],'speed' :'' ,
                'interface_data': {'ethernet_interfaces': {}, 'router_bgp_neighbors': {} } }
  for intf in interfaces:
    peer,pt,spd = get_connected_endpoints_gql(intf)
    if not peer: continue

    if "nw_ptp" in intf["tags"]:
      p2p_pt = get_ptp_port(sw_name,intf,peer,pt,spd)
    else:
      p2p_pt = get_p2p_port_gql(sw_name,intf,peer,pt,spd)
      if not p2p_pt: continue
      p2p_data['ips'].append( intf["ip_addresses"][0]["address"] )

    if not p2p_pt: continue

    MODULE_LOGGER.info(f"adding p2p port for == |{sw_name}| ---> { peer }/{pt} == {p2p_pt} ")
    p2p_data['intfs'].append ( list(p2p_pt.keys())[0] )
    p2p_data['peer_intfs'].append( pt )
    p2p_data['peer'].append( peer )
    p2p_data['speed'] = format_speed( intf["type"],sw_name+intf["name"])
    p2p_data['interface_data']['ethernet_interfaces'].update( p2p_pt )
  return p2p_data

def format_l3edge_data( interfaces,sw_name ):
  l3 = format_p2p_data( interfaces,sw_name )
  return l3

def format_tieline_data( interfaces,sw_name ):
  tie = format_p2p_data( interfaces,sw_name )
  if tie["speed"]:
    tie.update( {"speed" : format_speed(interfaces[0]["type"],sw_name+"TIE-LINE") } )
    del tie["interface_data"]
  return tie

def format_ptp_data( interfaces,sw_name ):
  ptp = format_p2p_data( interfaces,sw_name )
  if ptp['speed']:
    ptp_speeds = []
    for pp in ptp['interface_data']['ethernet_interfaces']:
      ptp_speeds.append(ptp['interface_data']['ethernet_interfaces'][pp]['speed'])
    ptp['speed'] = ptp_speeds
  return ptp

def get_connected_interface_gql(intf_id,gql):
  fields =   "{ name }"
  query = ("query {interface(id:%d) %s}" % (intf_id,fields))
  rr = requests.post(gql["url"], headers=gql["headers"], verify=False, json={"query": query})
  return rr.json()['data']['interface']['name']

def find_termination_id(intf_data):
  index1 = -1
  fmt_intfs =[]
  for intf in intf_data:
    index1 += 1
    intf_tags = [d["name"] for d in intf["tags"]]
    if not [g for g in intf_tags if 'nw_' in g]:
      MODULE_LOGGER.warning(f"NON - nw connections present{intf}")
      continue
    for id in intf['cable']['terminations']:
      if intf['cable_end'] != id['cable_end']:
        try:
          co_intf = [item for item in id['_device']['interfaces'] if item['id'] ==  str(id['termination_id'])][0]['name']
        except:
          MODULE_LOGGER.warning(f"Termination Error == {intf_data}")
        intf_data[index1].update({'connected_endpoint' : {'interface' : co_intf ,'name' : id['_device']['name'] }})
    intf_data[index1]["tags"] = intf_tags
    del intf_data[index1]['cable']
    fmt_intfs.append(intf_data[index1])
  return fmt_intfs

def get_p2p_interfaces_gql(gql,device):
  fields =   "{ name type ip_addresses {address} cable_end cable {terminations {cable_end termination_id _device {name interfaces {id name}}}} tags {name} }"
  query = ("query {interface_list(device:\"%s\",connected: true) %s}" % (device,fields))
  rr = requests.post(gql["url"], headers=gql["headers"], verify=False, json={"query": query})
  return find_termination_id( rr.json()['data']['interface_list'] )

def get_rt_fabric(gql,sw):
  rt_conn = {}
  sw_name = sw.name.upper()

  p2p_i = get_p2p_interfaces_gql( gql,sw_name )
  intfs = filter_interface_tags( p2p_i )

  p2p_data      = format_p2p_data( intfs["nw_p2p"],sw_name )
  l3_edge_data  = format_l3edge_data( intfs["nw_l3edge"],sw_name )
  tieline_data  = format_tieline_data( intfs["nw_tieline"],sw_name )
  ptp_data      = format_ptp_data( intfs["nw_ptp"],sw_name )

  bgp,network_services = format_custom_fields(sw.custom_fields)

  rt_conn = { 'bgp_as': bgp,
          'mgmt_ip': sw.primary_ip4.address,
          'platform': sw.device_type.model,
          'type' : sw.device_role.slug,
          'network_services' : network_services}
  if 'SP' in sw_name:
    rt_conn.update({ 'ptp_interfaces': ptp_data['intfs'],
            'ptp_peer_devices': ptp_data['peer'],
            'ptp_peer_interfaces': ptp_data['peer_intfs'],
            'ptp_link_interface_speeds': ptp_data['speed'],
            'l3edge_interfaces': l3_edge_data['intfs'],
            'l3edge_ip_addresses': l3_edge_data['ips'],
            'l3edge_peer_devices':l3_edge_data['peer'],
            'l3edge_peer_interfaces': l3_edge_data['peer_intfs'],
            'l3edge_link_interface_speeds': l3_edge_data['speed'],
            'tieline_interfaces': tieline_data['intfs'],
            'tieline_ip_addresses': tieline_data['ips'],
            'tieline_peer_devices':tieline_data['peer'],
            'tieline_peer_interfaces': tieline_data['peer_intfs'],
            'tieline_link_interface_speed': tieline_data['speed']})
  else:
    rt_conn.update({ 'p2p_link_interface_speed': p2p_data['speed'] ,
          'uplink_switches': p2p_data['peer'],
          'uplink_switch_interfaces': p2p_data['peer_intfs'],
          'uplink_interfaces': p2p_data['intfs'] ,
          'p2p_ip_addresses': p2p_data['ips'] , })
  return rt_conn

def write_prefix_vars(nb,folder):
  city = folder.split('/')[2]
  system = folder.split('/')[4]
  num_prefixes = 0
  MODULE_LOGGER.error(f"NETBOX VAR folder = {folder} --city- {city} -sys- {system}")
  pfx_dict = {'prefixes': {}}
  for sub_system in ['ctrl','rt']:
    network = system + '_' + sub_system
    pfx_dict['prefixes'].update({ sub_system : {} })
    if sub_system == 'ctrl':
      pfx_dict['prefixes'][sub_system].update( init_vlan_vrfs( nb.ipam.vrfs.filter(site=city,tag=network), city ) )
    else:
      pfx_dict['prefixes'][sub_system].update( {'l3_vlans' : {} } )
    prefixes = nb.ipam.prefixes.filter(site=city,tag=network)
    num_prefixes += len(prefixes)

    for pfx in prefixes:
      pfx_name = pfx.description
      pfx_name = pfx_name[pfx_name.find("[")+1:pfx_name.find("]")] if '[' in pfx_name else ''
      if sub_system == 'ctrl':
        if pfx.vlan and pfx.custom_fields:
          if pfx.custom_fields['VRF'] == None:
            MODULE_LOGGER.warning(f"PRefix has no vrf == {pfx}")
            pfx_dict['prefixes'][sub_system]['vrfs']['default'].update( add_vlan_info(pfx.vlan.name.upper(),pfx.prefix,pfx.vlan.vid ,pfx.custom_fields,pfx.vlan.custom_fields) )
            pfx_dict['prefixes'][sub_system]['vrfs']['default'].update( { 'vrf_vni' : 1080 } )
          elif pfx.custom_fields['VRF'] == 'l2vlans':
            pfx_dict['prefixes'][sub_system]['l2vlans'].update( add_vlan_info(pfx.vlan.name.upper(),pfx.prefix,pfx.vlan.vid ,pfx.custom_fields,pfx.vlan.custom_fields) )
          elif pfx.custom_fields['VRF'] == 'l2mgmt':
            pfx_dict['prefixes'][sub_system]['l2mgmt'].update( add_vlan_info(pfx.vlan.name.upper(),pfx.prefix,pfx.vlan.vid ,pfx.custom_fields,pfx.vlan.custom_fields) )
          else:
            MODULE_LOGGER.warning(f"PREFIX == {pfx.custom_fields['VRF']} ++ {pfx}")
            pfx_dict['prefixes'][sub_system]['vrfs'][pfx.custom_fields['VRF']].update( add_vlan_info(pfx.vlan.name.upper(),pfx.prefix,pfx.vlan.vid ,pfx.custom_fields,pfx.vlan.custom_fields) )
        else:
          pfx_dict = add_prefixes(pfx_dict,pfx,pfx_name,sub_system)
      elif sub_system == 'rt':
        if pfx.vlan and pfx.custom_fields:
          pfx_dict['prefixes'][sub_system]['l3_vlans'].update({ pfx.vlan.name:{ 'prefix' : pfx.prefix , 'vlan' : pfx.vlan.vid , 'network_services' : [ pfx.custom_fields['networkservicetags'] ] } })
        if pfx_name:
          pfx_dict = add_prefixes(pfx_dict,pfx,pfx_name,sub_system)

  write_yaml_file(folder+'/prefixes.yml',pfx_dict)
  return num_prefixes

def add_prefixes(pfx_dict,pfx,pfx_name,sub_system):
  try:
    pfx_dict['prefixes'][sub_system][pfx_name]['prefix'].append(pfx.prefix)
  except:
    pfx_dict['prefixes'][sub_system].update({ pfx_name: { 'prefix' : [pfx.prefix]  } })
  return pfx_dict

def init_vlan_vrfs(ctrl_vrfs,city):
  dc = {'vrfs' : { 'default' : {} }, 'l2vlans' : {},'l2mgmt' : {} }
  for vrf in ctrl_vrfs:
    if vrf.custom_fields['site'].lower() != city : continue
    dc['vrfs'].update({ vrf.name : {} })
  for vrf in ctrl_vrfs:
    if vrf.custom_fields['site'].lower() != city : continue
    dc['vrfs'][vrf.name ].update({ 'rd' : vrf.rd , 'vrf_vni' : int(vrf.custom_fields['vni']) })
  return dc

def add_vlan_info(name,pf,vl,cf,vlcf):
  dc = {name:{ 'prefix' : pf , 'vlan' : vl , 'vrf' : cf['VRF'], 'networkservicetags' :  cf['networkservicetags'] }}
  if vlcf['multicast']: dc[name].update({'multicast' : vlcf['multicast']})
  if vlcf['igmp_flooding']: dc[name].update({'igmp_flooding' : vlcf['igmp_flooding']})
  if vlcf['ip_helpers']: dc[name].update({'ip_helpers' : [s.strip() for s in (vlcf['ip_helpers']).split(',')]})
  return dc

def get_checksum(net, subs, locations):
  output_files = []
  output_files.append(locations['vars']+'/prefixes.yml')

  for sub in subs:
    output_files.append(locations[sub] + '/hosts.yml')

  hash_md5 = hashlib.md5()
  for filename in output_files:
    try:
      with open(filename, 'rb') as inputfile:
        data = inputfile.read()
        hash_md5.update(data)
    except Exception as e:
      print('no-file {}',e)
      # hash_md5.update('no')

  return hash_md5.hexdigest()

def main_orig():
  module = AnsibleModule(
    argument_spec=dict(
      nb_host=dict(type='str', required=True),
      token=dict(type='str', required=True),
      network=dict(type='str', required=True),
      sub_networks=dict(type='list', required=True),
      locations=dict(type='dict', required=True),
    ),
    supports_check_mode=True,
  )
  main_start = time.time()

  nb_host = module.params['nb_host']
  token = module.params['token']
  network = module.params['network']
  sub_networks = module.params['sub_networks']
  locations = module.params['locations']

  nb = pynetbox.api(nb_host,token)
  nb.http_session.verify = False

  gql = {
    'url' : nb_host+'/graphql/',
    'headers' : {'Authorization': f"Token {token}" }
  }

  hash1 = 1 #get_checksum(network,sub_networks,locations)

  num_prefixes = write_prefix_vars(nb,locations['vars'])
  for sub_network in sub_networks:
    write_inventory(gql,nb,network,sub_network,locations)

  MODULE_LOGGER.warning(f"TOTAL DURATION = { (time.time() - main_start)/ 60 } minutes")
  hash2 = 2 # get_checksum(network,sub_networks,locations)

  if (hash1 == hash2):
    module.exit_json(changed=False, msg=f"Received {num_prefixes} prefixes from NetBox, url= {module.params['nb_host']}")
  else:
    module.exit_json(changed=True, msg=f"Received {num_prefixes} prefixes from NetBox, url= {module.params['nb_host']}")

def main():
  module = AnsibleModule(
    argument_spec=dict(
      nb_host=dict(type='str', required=True),
      token=dict(type='str', required=True),
    ),
    supports_check_mode=True,
  )
  main_start = time.time()

  nb_host = module.params['nb_host']
  token = module.params['token']

  nb = pynetbox.api(nb_host,token)
  nb.http_session.verify = False

  #gql = {
  #  'url' : nb_host+'/graphql/',
  #  'headers' : {'Authorization': f"Token {token}" }
  #}

  devices=nb.dcim.devices.all()
  #fmt = "{:<20}{:<20}{:<30}{:<60}"
  #header = ("Name", "Device Role", "Description", "Config Context")
  #print(fmt.format(*header))
  for dev in devices:
      print(dev.name)

  module.exit_json(changed=False, msg=f"Received from NetBox, url= {module.params['nb_host']}")

if __name__ == "__main__":
  main()
