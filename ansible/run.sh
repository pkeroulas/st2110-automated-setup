#!/bin/bash

docker_run () {
    docker run --rm -it -v ${PWD}:/projects deplops/avdbase:3.8.5
}

upload='./playbooks/upload.yml'
flush='./playbooks/flush.yml'
inventory_sw="-i ./inventories/switch/hosts.yml"
inventory_gw="-i ./inventories/gateways/hosts.yml"
ansible="ansible-playbook"

echo "Cmd exemple:
$ansible $sw_inventory $upload
$ansible $sw_inventory $flush
$ansible $gw_inventory $upload
"
docker_run
