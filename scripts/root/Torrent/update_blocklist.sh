#!/bin/bash

LOG_FILE="/root/update.log"
BLOCKLIST_DIR="/home/transmission/.config/transmission-daemon/blocklists"

BL_FILE_LIST="level1 level2 level3 templist ads rangetest spyware hijacked"
BL_ARRAY=( $BL_FILE_LIST )
# Number of blocklists to update
BL_CNT=${#BL_ARRAY[@]}
# Count number of successful blocklist updates
SUCCESS_CNT=0

if [ -f $LOG_FILE ]; then
	# Log the start of operations
	echo " " >> $LOG_FILE
	echo "==================================================" >> $LOG_FILE
	echo "===== Update Transmission blocklists - Start =====" >> $LOG_FILE
	date >> $LOG_FILE
	echo "Attempting to download and update" $BL_CNT "blocklist files" >> $LOG_FILE
	echo "" >> $LOG_FILE

	# Change into the correct directory
	cd $BLOCKLIST_DIR

	if [ $? -eq 0 ]; then
		# For each of the files we're interested in:
		for CUR_BL_FILE in $BL_FILE_LIST
		do
			OUTFILE=$CUR_BL_FILE".gz"
			URL="http://list.iblocklist.com/?list=bt_"$CUR_BL_FILE"&fileformat=p2p&archiveformat=gz"
			
			# Remove old blocklist files
			if [ -f $CUR_BL_FILE ]; then
				echo "Removing old blocklist file:" $CUR_BL_FILE >> $LOG_FILE
				rm $CUR_BL_FILE*
			fi
			
			# Remove old output file
			if [ -f $OUTFILE ]; then
				echo "Removing old output file:" $OUTFILE  >> $LOG_FILE
				rm $OUTFILE
			fi

			# If no blocklist file, get new one
			if [ ! -f $CUR_BL_FILE ]; then
				wget -4 -O $OUTFILE $URL
				
				if [ -f $OUTFILE ]; then
					echo "Successfully downloaded" $OUTFILE", extracting" >> $LOG_FILE
					gunzip $OUTFILE
					
					# Determine if extraction was successful
					if [ $? -eq 0 ]; then
						chmod go+r $CUR_BL_FILE
						chown transmission:users $CUR_BL_FILE
						SUCCESS_CNT=$(($SUCCESS_CNT+1))
					else
						echo "Error extracting" $OUTFILE", aborting for this blocklist" >> $LOG_FILE
						
						# Delete the downloaded file to keep things clean
						rm $OUTFILE
					fi
				else
					echo "Error downloading" $OUTFILE", aborting for this blocklist" >> $LOG_FILE
				fi
			fi
		done

		echo "" >> $LOG_FILE
		echo "Successfully updated" $SUCCESS_CNT "of" $BL_CNT "blocklists" >> $LOG_FILE
		if [ $SUCCESS_CNT -gt 0 ]; then
			echo "Restarting Transmission" >> $LOG_FILE
		 	systemctl restart transmission
			echo "Done restarting transmission" >> $LOG_FILE
		else
			echo "Too many errors, not restarting Transmission" >> $LOG_FILE
		fi
		
		cd - 2>&1 >/dev/null
	else
		echo "Unable to change to" $BLOCKLIST_DIR", aborting" >> $LOG_FILE
	fi

	# Log the end of operations
	echo "" >> $LOG_FILE
	date >> $LOG_FILE
	echo "=====  Update Transmission blocklists - End  =====" >> $LOG_FILE
	echo "" >> $LOG_FILE
fi
# If the LOG_FILE doesn't exist, we can't do anything
