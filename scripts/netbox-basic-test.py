#!/usr/bin/python

import pynetbox
from pprint import pprint

NETBOX='http://10.164.50.135:2000'
# API tocken create in the web UI with superuser but
# could habe been created from: nb.create_token(user, password)
TOKEN='036f9bbb609c6c887d5ad5b18f70d616d58a4109'
nb = pynetbox.api(NETBOX, TOKEN)
nb.http_session.verify = False
nb.version

devices=nb.dcim.devices.filter(devicetype="embox-6-u")
fmt = "{:<20}{:<20}{:<20}"
header = ("Name", "Device Role", "Description")
print(fmt.format(*header))
for dev in devices:
    print(
        fmt.format(
            dev.name,
            str(dev.device_role.name),
            dev.description,
        )
    )
