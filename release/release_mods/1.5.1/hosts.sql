DROP TABLE IF EXISTS hosts_old151;
CREATE TABLE hosts_old151 AS SELECT * FROM hosts;
DROP TABLE hosts;
CREATE TABLE IF NOT EXISTS hosts(id int auto_increment, ip varchar(45) NOT NULL, hostname varchar(255) NOT NULL, insertdate datetime NOT NULL DEFAULT CURRENT_TIMESTAMP, updatedate datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, hostinfo varchar(4096) NOT NULL, primary key(id), unique key(ip));

