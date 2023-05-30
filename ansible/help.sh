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

RED='\033[0;31m'
BROWN='\033[0;33m'
NC='\033[0m'

echo_instruction(){
    printf "${BROWN}%s${NC}\n" "$@"
}

echo_cmd(){
    printf "   ${BROWN}%s${NC} - %-15.15s : %s\n" "$1" "$2" "$3"
}

execute() {
    echo "$@"
    echo_instruction "[ENTER]"
    read r
    $@
    echo_instruction "[ENTER]"
    read r
}

while true
do
    clear
    echo "========================================
Ansible cmd examples:"
    echo_cmd 1 "Switch"    "$cmd_1"
    echo_cmd 2 "Gateways"  "$cmd_2"
    echo_cmd 3 "DHCP conf" "$cmd_3"
    echo_cmd q "Quit"
    echo_instruction "[Select the cmd + ENTER]"
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

