DROP TABLE IF EXISTS debugrequests_old153;
CREATE TABLE debugrequests_old153 AS SELECT * FROM debugrequests;
DROP TABLE debugrequests;
CREATE TABLE IF NOT EXISTS debugrequests(id int auto_increment, hostname VARCHAR(255) NOT NULL, state VARCHAR(20) NOT NULL, insertdate int NOT NULL, updatedate int NOT NULL, primary key(id));
INSERT INTO debugrequests (id, hostname, state, insertdate, updatedate) SELECT id, hostname, state, insertdate, updatedate FROM debugrequests_old153;