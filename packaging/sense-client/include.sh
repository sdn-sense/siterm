#!/bin/bash

WDIR=`dirname "$0"`

source $WDIR/secrets.sh

function get_input(){
   while getopts "f:sh:p:v" opt; do
      case $opt in
         f) 
           INPUT_FILE=${OPTARG};;
         s) 
           PROTOCOL_NAME="https";;
         h)
           REMOTE_IP=${OPTARG};;
         p)
           REMOTE_PORT=${OPTARG};;
         v)
           VERBOSE="1";;
         esac  
   done
              
   if [ -z $PROTOCOL_NAME ]; then
      PROTOCOL_NAME="http"
   fi

   if [ -z $REMOTE_IP ]; then
      REMOTE_IP="127.0.0.1"
   fi
        
   if [ -z $REMOTE_PORT ] && [[ $PROTOCOL_NAME == https ]]; then
      REMOTE_PORT="8443"

   elif [ -z $REMOTE_PORT ]; then
      REMOTE_PORT="8080"
   fi
}

function get_token() {
   export TOKEN=$(curl -s -k \
      https://k152.maxgigapop.net:8543/auth/realms/StackV/protocol/openid-connect/token \
      -d "grant_type=password" \
      -d "client_id=StackV"  \
      -d "username=$SENSE_USERNAME" \
      -d "password=$SENSE_PASSWORD" \
      -d "client_secret=$SENSE_CLIENT_SECRET" \
      | cut -d\" -f4)
   echo $TOKEN   
}

function curl_exec_auth(){
   ENDTIME=$(date +%s)
   
   if [ -z $TOKEN ] || [ -z $STARTTIME ] || [ $(($STARTTIME - $ENDTIME)) > 59 ]; then
      STARTTIME=$(date +%s)
      JSON=$(curl -s -k \
      https://k152.maxgigapop.net:8543/auth/realms/StackV/protocol/openid-connect/token \
      -d "grant_type=password" \
      -d "client_id=StackV"  \
      -d "username=$SENSE_USERNAME" \
      -d "password=$SENSE_PASSWORD" \
      -d "client_secret=$SENSE_CLIENT_SECRET")

      export TOKEN=$(echo $JSON | jq -r .access_token)

      export REFRESH=$(echo $JSON | jq -r .refresh_token)
   fi

   for last; do true; done
   
   
   if [[ -z $VERBOSE ]]; then
      CURL_TEMP="curl -k -X"
   else
      CURL_TEMP="curl -k -v -X"
   fi

   for var in "$@"
   do
      if [[ $var != $last ]]; then
         CURL_TEMP="${CURL_TEMP} $var"
      fi   
   done   

   CURL_TEMP="${CURL_TEMP} -H \"Authorization: bearer $TOKEN\" -H \"Refresh: $REFRESH\""   

   CURL_TEMP="${CURL_TEMP} $PROTOCOL_NAME://$REMOTE_IP:$REMOTE_PORT/StackV-web/restapi"
   CURL_TEMP="${CURL_TEMP}$last"
   #CURL_TEMP="${CURL_TEMP} 2>/dev/null"
   CURL_TEMP="${CURL_TEMP}"
  
   #used to test if it is possible to return output of eval as a variable
   RET=$(eval $CURL_TEMP)
   echo $RET
}
