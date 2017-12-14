#!/bin/bash

path='/edx/app/lrs/'
logpath='/edx/var/log/tracking/'
exportpath='/edx/app/lrs/raw-log/'
apipath='/edx/app/lrs/api-json/'
now=$(date -u +'%Y-%m-%dT%H:00:00')
previous=$(date -u -d '1 hour ago' +'%Y-%m-%dT%H:00:00')
log=$(date -d '1 hour ago'  +'%Y-%m-%d_HKT%H')


#Step 1 - Filter hourly log from original edx tracking log
echo "START_PERIOD@UTC: " $previous " END_PERIOD@UTC: " $now
nodejs $path'edxlogfilter.js' $logpath'tracking.log' $logpath'tracking.log.backup' $previous $now $exportpath$log'.log'


#Step 2 - Convert Edx raw log to xapi log standard
python $path'edx_to_xapi.py' $exportpath$log'.log' > $apipath$log'.json'

#Step 3 - Send xapi record to lrs
#nodejs $path'xapi_to_lrs.js' $apipath$log'.json' >> $apipath'fail.json'

