CREATE TABLE IF NOT EXISTS `callvote` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `client_id` int(11) unsigned NOT NULL,
  `cv_type` varchar(20) NOT NULL,
  `cv_data` varchar(40) DEFAULT NULL,
  `max_num` smallint(2) unsigned NOT NULL,
  `num_yes` smallint(2) unsigned NOT NULL,
  `num_no` smallint(2) unsigned NOT NULL,
  `time_add` int(11) unsigned NOT NULL,
  PRIMARY KEY (`id`),
  KEY `client_id` (`client_id`)
) ENGINE=MyISAM  DEFAULT CHARSET=utf8 AUTO_INCREMENT=1 ;