#!/bin/bash

upload_sw='./playbooks/upload_sw_config.yml'
upload_gw='./playbooks/upload_gw_config.yml'
upload_dhcp='./playbooks/dhcp_config.yml'
flush='./playbooks/flush.yml'
inventory_sw="-i ./inventories/switch/hosts.yml"
inventory_gw="-i ./inventories/gateways/hosts.yml"
ansible="ansible-playbook"

cmd_1="$ansible $inventory_sw $upload_sw"
cmd_2="$ansible $inventory_gw $upload_gw"
cmd_3="$ansible $inventory_gw $upload_dhcp"

execute() {
    echo "$@"
    echo "[ENTER]"
    $@
    echo "[ENTER]"
    read r
}

# TODO add colors

while true
do
    clear
    echo "========================================
Ansible cmd examples:
    1 Switch:    $cmd_1
    2 Gateways:  $cmd_2
    3 DHCP conf: $cmd_3
    q Quit
    "

    read i

    case $i in
        1)
            execute $cmd_1
            ;;
        2)
            execute $cmd_2
            ;;
        3)
            execute $cmd_3
            ;;
        q)
            exit
            ;;
        *)
            echo "????????"
            sleep 1
    esac
done

