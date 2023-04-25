#!/usr/bin/python

import pynetbox
from pprint import pprint

# TODO don't hardcode the IP
NETBOX='http://10.164.50.135:2000'

# API tocken create in the web UI with 'smpte' user but
# could habe been created from: nb.create_token(user, password)
TOKEN='18db3f77e7fce958f1dff8aadb655636216cc859'
nb = pynetbox.api(NETBOX, TOKEN)
nb.http_session.verify = False
nb.version

devices=nb.dcim.devices.filter(device_type="embox-6-u")
fmt = "{:<20}{:<20}{:<30}{:<60}"
header = ("Name", "Device Role", "Description", "Config Context")
print(fmt.format(*header))
for dev in devices:
    print(
        fmt.format(
            dev.name,
            str(dev.device_role.name),
            dev.description,
            str(dev.config_context) # json in NB -> dict in pynetbox
        )
    )
    ifaces = list(nb.dcim.interfaces.filter(device=dev.name))
    for iface in ifaces:
        print("    - iface: {}, mac: {}".format(iface.name, iface.mac_address))

