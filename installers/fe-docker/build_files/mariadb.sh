#!/bin/sh
if [ ! -f /var/lib/mysql/site-rm-db-initialization ]; then
  # First time start of mysql, ensure dirs are present;
  mkdir -p /var/lib/mysql
  mkdir -p /var/log/mariadb
  chown -R mysql:mysql /var/lib/mysql
  chown mysql:mysql /var/log/mariadb

  # Initialize the mysql data directory and create system tables
  mysql_install_db --user mysql > /dev/null

  # Start mysqld in safe mode and sleep 5 sec
  mysqld_safe --user mysql &
  sleep 5s

  # Replace variables in /root/mariadb.sql with vars from ENV (docker file)
  sed -i "s/##ENV_MARIA_DB_PASSWORD##/$MARIA_DB_PASSWORD/" /root/mariadb.sql
  sed -i "s/##ENV_MARIA_DB_USER##/$MARIA_DB_USER/" /root/mariadb.sql
  sed -i "s/##ENV_MARIA_DB_HOST##/$MARIA_DB_HOST/" /root/mariadb.sql
  sed -i "s/##ENV_MARIA_DB_DATABASE##/$MARIA_DB_DATABASE/" /root/mariadb.sql

  # Execute /root/mariadb.sql
  mysql -v < /root/mariadb.sql
  sleep 5s

  # Kill mysql and restart it again
  ps -wef | grep mysql | grep -v grep | awk '{print $2}' | xargs kill -9

  mysqld_safe --user mysql &> /var/log/mariadb/startup &
  sleep 5s

  # Create all databases needed for SiteRM
  python3 -c 'from DTNRMLibs.DBBackend import DBBackend; db = DBBackend(); db._createdb()'

  # create file under /var/lib/mysql which is only unique for Site-RM. 
  # This ensures that we are not repeating same steps during docker restart
  echo `date` >> /var/lib/mysql/site-rm-db-initialization
else
  echo "Seems this is not the first time start. Will not create DB again"
  mysqld_safe --user mysql &> /var/log/mariadb/startup &
  sleep 5s
  # Create all databases if not exists needed for SiteRM
  python3 -c 'from DTNRMLibs.DBBackend import DBBackend; db = DBBackend(); db._createdb()'
fi
