WDIR=`dirname "$0"`

source $WDIR/include.sh

get_input $@

shift $(($OPTIND - 1))

instance_id=$1

# get service manifest (after service becomes CREATE - READY)
# ./manifest.sh -s -h 179-132.research.maxgigapop.net -f manifest-1.xml 2d443305-fb11-47de-8d02-66bd823b3c47

ret=$(curl_exec_auth "POST" "-d @$WDIR/$INPUT_FILE" "--header \"Content-Type:application/xml\""  "/service/manifest/$instance_id")
echo $ret
