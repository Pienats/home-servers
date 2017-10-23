# Synopsis
Code library to automate torrent downloading via VPN.
The code checks:
* If the current run falls within an interval to check for new torrents
* if there are new/existing torrents

If either of the above is true:
* Check if the VPN is up
* Check if the VPN has connectivity

If either of the above is false, an attempt to restart the VPN is made

If there are active torrents (new/existing):
* Make sure that the torrenting client is configured to bind to the VPN address
* If the VPN address is different from the torrent client configuration:
  - Stop the torrent client
  - Update torrent client configuration
  - Start the torrent client
  
If there are no active torrents, stop the torrent client and the VPN

# Required libraries
* Python
* Bash
* "ip" utilities

# Additional software requirements
Specifically the following additional python libraries are needed
* dev-python/netifaces

# Tested platforms
This code has only been tested on Gentoo Linux
