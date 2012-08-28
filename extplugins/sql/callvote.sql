CREATE TABLE IF NOT EXISTS `callvotelog` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `client_id` int(11) unsigned NOT NULL,
  `type` varchar(20) NOT NULL,
  `data` varchar(40) DEFAULT NULL,
  `yes` smallint(2) unsigned NOT NULL,
  `no` smallint(2) unsigned NOT NULL,
  `time_add` int(11) unsigned NOT NULL,
  PRIMARY KEY (`id`),
  KEY `client_id` (`client_id`)
) ENGINE=MyISAM  DEFAULT CHARSET=utf8 AUTO_INCREMENT=1 ;