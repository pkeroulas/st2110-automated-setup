#!/bin/bash

docker_run () {
    docker run --rm -it -v ${PWD}:/projects deplops/avdbase:3.8.5
}

upload='./playbooks/upload_config.yml'
flush='./playbooks/flush.yml'
inventory_sw="-i ./inventories/switch/hosts.yml"
inventory_gw="-i ./inventories/gateways/hosts.yml"
ansible="ansible-playbook"

echo "Cmd exemple:
$ansible $inventory_sw $upload
$ansible $inventory_sw $flush
$ansible $inventory_gw $upload
"
docker_run
