 #!/bin/bash

IFACE_MGT=eno1
IFACE_INFRA=enx00e04c0208a4
IP_SW=192.168.0.1
PORT_NETBOX=2000
PORT_MNSET=4000
PORT_GLASS=3000
PORT_NMOS=8000
IP_MGT=$(ip addr show $IFACE_MGT | tr -s ' ' | sed -n 's/ inet \(.*\)\/.*/\1/p' | head -n1)

if [ "$1" = '-v' ]; then
    set -x
fi

show_header()
{
    echo "-----------------------------------------------"
    printf "   \e[1;29m%s\e[m\n" "$1"
    echo "-----------------------------------------------"
}

show_status()
{
    if [ "$2" = 'UP' ]; then
        color=32 #green
        len=5
    elif [ "$2" = 'DOWN' ]; then
        color=31 #red
        len=5
    else
        color=34 #blue
        len=25
    fi
    printf  "%-30.30s \e[1;${color}m%-${len}.${len}s \e[1;34m%-25.25s %s\e[m\n" "$1" "$2" "$3" "$4"
}

get_status()
{
    if $2 2>&1 | grep -q "$3"; then
        ret="UP"
    else
        ret="DOWN"
    fi
    show_status "$1" "$ret" $4
}

port_status()
{
    name=$1
    iface=$2
    ips=$(ip addr show $iface | tr -s ' ' | sed -n 's/ inet \(.*\)\/.*/\1/p')
    gw=$(ip route | sed -n 's/default via \(.*\) dev '""$(echo $iface | tr -d '\n')""' .*/\1/p' | head -n1)

    #maybe
    #switch_name=$(lldpcli show neighbors port $iface | tr -s ' ' | sed -n 's/.*SysName: \(.*\)/\1/p')
    #switch_ip=$(lldpcli show neighbors port $iface | tr -s ' ' | sed -n 's/.*MgmtIP: \(.*\)/\1/p')
    #media_gw_port=$(lldpcli show neighbors port $iface | tr -s ' ' | sed -n 's/.*PortID: \(.*\)/\1/p')
    show_header "Network interface: $name"
    get_status "Link" "ip addr show $iface" "$iface.* UP" "$iface"
    for ip in $ips; do
        get_status "IP" "ping -c 1 -W 1 $ip" "1 received" "$ip"
    done
    get_status "GW" "ping -c 1 -W 1 $gw" "1 received" "$gw"
}

get_all_status()
{
    port_status "Management" $IFACE_MGT
    get_status  "Internet" "ping -I $IFACE_MGT -c 1 -W 1 8.8.8.8" "1 received"

    port_status "Switch" $IFACE_INFRA
    get_status "IP" "ping -c 1 -W 1 $IP_SW" "1 received" "switch $IP_SW"

    dockerz=$(docker ps)

    show_header "Net services"
    get_status "Docker: ISC DHCP"       "echo $dockerz" "dhcp"
    get_status "Docker: DHCP Glass" "echo $dockerz" "server-glass"
    get_status "Web $IP_MGT:$PORT_GLASS" "curl http://$IP_MGT:$PORT_GLASS 2>/dev/null" "Glass | ISC DHCP Server"
    get_status "Docker: NMOS registry" "echo $dockerz" "nmos-registry-1"
    get_status "Web $IP_MGT:$PORT_NMOS" "curl http://$IP_MGT:$PORT_NMOS 2>/dev/null" "admin.*schema.*x-nmos"

    show_header "Netbox"
    get_status "Docker: Netbox" "echo $dockerz" "netbox-netbox-1"
    get_status "Docker: Netbox Worker" "echo $dockerz" "netbox-netbox-worker-1"
    get_status "Docker: Postgres" "echo $dockerz" "netbox-postgres-1"
    get_status "Docker: Reddis" "echo $dockerz" "netbox-redis-1"
    get_status "Docker: Reddis Cache" "echo $dockerz" "netbox-redis-cache-1"
    get_status "Docker: Housekeeping" "echo $dockerz" "netbox-netbox-housekeeping-1"
    get_status "Web $IP_MGT:$PORT_NETBOX" "curl http://$IP_MGT:$PORT_NETBOX 2>/dev/null" "Home | NetBox"

    show_header "Riedel Tools"
    get_status "MNSET java" "ps aux" "[j]ava"
    get_status "MNSET mongo" "ps aux" "[m]ongod"
    get_status "MNSET $IP_MGT:$PORT_MNSET" "curl http://$IP_MGT:$PORT_MNSET 2>/dev/null" "MN SET"
}

get_all_status
set +x
