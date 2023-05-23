#!/bin/bash

docker_run () {
    docker run --rm -it -v ${PWD}:/projects deplops/avdbase:3.8.5
}

upload_sw='./playbooks/upload_sw_config.yml'
upload_gw='./playbooks/upload_gw_config.yml'
flush='./playbooks/flush.yml'
inventory_sw="-i ./inventories/switch/hosts.yml"
inventory_gw="-i ./inventories/gateways/hosts.yml"
ansible="ansible-playbook"

echo "Cmd exemple:
$ansible $inventory_sw $upload_sw
$ansible $inventory_sw $flush

$ansible $inventory_gw $upload_gw
"
docker_run
