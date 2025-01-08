DROP TABLE IF EXISTS hosts_old151;
CREATE TABLE hosts_old151 AS SELECT * FROM hosts;
DROP TABLE hosts;
CREATE TABLE IF NOT EXISTS hosts(id int auto_increment, ip varchar(45) NOT NULL, hostname varchar(255) NOT NULL, insertdate int NOT NULL, updatedate int NOT NULL, hostinfo varchar(4096) NOT NULL, primary key(id), unique key(ip));
DROP TABLE IF EXISTS servicestates_old151;
CREATE TABLE servicestates_old151 AS SELECT * FROM servicestates;
DROP TABLE servicestates;
CREATE TABLE IF NOT EXISTS servicestates(id int auto_increment, hostname VARCHAR(255) NOT NULL, servicename VARCHAR(50) NOT NULL, servicestate VARCHAR(50) NOT NULL, runtime int NOT NULL, version VARCHAR(50) NOT NULL, updatedate int NOT NULL, exc varchar(4096) NOT NULL, primary key(id))
