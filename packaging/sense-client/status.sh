WDIR=`dirname "$0"`

source $WDIR/include.sh

get_input $@

shift $(($OPTIND - 1))

SERVICE_UUID=$1

# commit service -- MAKE SURE TO CHANGE THE UUID PER INSTANCE
# ./status.sh -s -h 179-132.research.maxgigapop.net 2d443305-fb11-47de-8d02-66bd823b3c47

ret=$(curl_exec_auth "GET" "--header \"Content-Type:application/json\""  "/sense/service/$SERVICE_UUID/status")

echo $ret

