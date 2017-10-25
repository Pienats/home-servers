# Synopsis
Code library to automate torrent downloading via VPN.
The code checks:
* If the current run falls within an interval to check for new torrents
* if there are new/existing torrents

If either of the above is true:
* Check if the VPN is up
* Check if the VPN has connectivity
* If this fails, an attempt to restart the VPN is made

If the run is in a Flexget interval:
* Run flexget to check for any new torrents

If there are active torrents (new/existing):
* Make sure that the torrenting client is configured to bind to the VPN address
* If the VPN address is different from the torrent client configuration:
  - Stop the torrent client
  - Update torrent client configuration
  - Start the torrent client
  
If there are no active torrents, stop the torrent client and the VPN

# Setup and configuration
Note: The idea is to run these activities as the "transmission" user. The iptables rules trigger on this user, and routes only this user's traffic through the VPN. As the transmission user does not necessarily have a shell specified, the commands are recommended to be run from the root acount, or at least within a "sudo" command.

## "Installing" the server scripts
Simply clone the git repo to an appropriate location.

## Directory ownership update
As root (this might need to be done at various times during setup, to update ownership of new configuration files):
* `chown -R <transmission user>:<transmission group> /var/lib/<transmission dir>`

## Install required system packages/libraries
Install the following packages using the system package manager
* python3 (specifically v3.3 or higher)
* python<3>-netifaces
* python<3>-pip
* openvpn
* iptables
* tranmsmission
* iproute2

Ubuntu: `sudo apt-get install python3 python3-netifaces python3-pip openvpn iptables transmission-daemon iproute2`

Gentoo: `emerge -va dev-lang/python dev-python/netifaces dev-python/pip net-vpn/openvpn net-firewall/iptables net-p2p/transmission sys-apps/iproute2`

## Update system configuration files
### sysctl.d configuration files
Create the following `/etc/sysctl.d/` config files:

96-vpn.conf (Please update the network interface ID to the correct value):
```
net.ipv4.conf.all.rp_filter = 0
net.ipv4.conf.default.rp_filter = 0
net.ipv4.conf.eth0.rp_filter = 0
```

97-transmission.conf
```
net.core.rmem_max=4194304
net.core.wmem_max=1048576
```

Then run:
* `sysctl -p /etc/sysctl.d/96-vpn.conf` (this will allow policy based routing)
* `sysctl -p /etc/sysctl.d/97-transmission.conf` (this will set the memory buffer sizes as required by transmission)

### Create the alternate routing table
Add the following line to `/etc/iproute2/rt_tables`:
```
200		<vpn table name>
```
This will create the alternate routing table used for the policy based routing.

## Create/Update OpenVPN configuration files
It is assumed that the user knows how to appropriately set up the OpenVPN configuration files to achieve the following:
* Start the required OpenVPN tunnel as a startup service
* Automatically specify authentication information
* Specify the tunnel interface ID to use (eg `tun0`)

It might be necessary to add `route-nopull` to the OpenVPN configuration file to avoid automatic routing information updates. These server scripts automatically set up an alternate routing table to which "transmission" related traffic is routed to via IP rules and iptables entries.

### OpenVPN file locations
* Gentoo (OpenRC): `/etc/openvpn/`
* Ubuntu (systemd): `/etc/openvpn/`

## Transmission configuration
* Depending on the system being used, `</transmission/config/dir/>` is most likely one of the following:
  - `/var/lib/<transmission dir>/config`
  - `/var/lib/<transmission dir>/.config/transmission-daemon`

The remainder of this guide will simply refer to `</transmission/config/dir/>`
* Start the Transmission daemon to create `</transmission/config/dir>/settings.json`
* Edit `</transmission/config/dir>/settings.json` to update the config to your liking
* Add the following lines to `/var/lib/<transmission dir>/config/settings.json`:
```
"watch-dir": "<path/where/flexget/will/download/new/torrents/>", 
"watch-dir-enabled": true
```
NOTE: If it does not yet exist, create the `watch-dir` and set the ownership to the transmission user

## Flexget configuration
Install Flexget for the "transmission" user using pip
* `su -l <transmission user> -s /bin/bash -c "pip[2,3] install flexget`

Update the Flexget configuration
* `mkdir /var/lib/<transmission dir>/.flexget`
* Create `/var/lib/<transmission dir>/.flexget/config.yml` ([Flexget webpage](https://flexget.com/Configuration as a guidline))
* For the download plugin:
  - Do **not** use `transmission: yes`
  - Specify `download: </path/to/transmission/watch/dir/>`
NOTE: Set the directory ownership as specified above

## Server script configuration
The server scripts use an "ini" style configuration file. Create a new server configuraion file with the following fields:
(update the values in <> to match your system; it should not be necessary to use quotes for the values)
```
[DEFAULT]
InitSystem = <openRC/systemd>

[VPN]
Provider = <VPN service provider (should match the initsystem configuration name, excluding required OS fields; eg vpnarea)>
Interface = <Tunnel interface device ID (this can be fixed in the OpenVPN configuration); eg tun0>
PingOne = <To test the VPN connection, certain VPN providers do not respond to pings to the peer address, set to True here to ping x.x.x.1 instead>
RoutingTable = <vpn table name>
Mark = <Mark ID to use for the Transmission user in hexadecimal format; eg 0x2>
User = <Tranmssion user; eg transmission or debian-transmission>

[Torrents]
HomePath = <transmission user home dir; eg /var/lib/transmission/>
AddedPath = </path/to/transmission/watch/dir/>
ActivePath = <path to active transmission torrents; typically ${HomePath}/config/torrents/>
ConfigFile = <path to transmission configuration file; typically ${HomePath}/config/settings.json>
DaemonName = <system transmission daemon name; eg transmission or transmission-daemon>

[Flexget]
FlexgetBin = <Flexget binary; typically ${Torrents:HomePath}/.local/bin/flexget>
```

# Tested platforms
This code has only been tested on Gentoo Linux and Ubuntu. Minor modifications might be needed for other distributions; Arch Linux systemd, for example, handles OpenVPN configuration slightly differently.

# Run the scripts (testing the setup)

# Set up cronjob
