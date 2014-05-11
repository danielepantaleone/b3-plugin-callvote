#
# Callvote Plugin for BigBrotherBot(B3) (www.bigbrotherbot.net)
# Copyright (C) 2013 Daniele Pantaleone <fenix@bigbrotherbot.net>
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#
# CHANGELOG
#
#   2014/05/10 - 1.11 - Fenix
#   - added SQLite compatibility
#   - rewrote dictionay creation as literals
#   - use the built in getCmd function if available

__author__ = 'Fenix'
__version__ = '1.11'

import b3
import b3.plugin
import b3.events
import re
import time

from ConfigParser import NoSectionError

try:
    # import the getCmd function
    import b3.functions.getCmd as getCmd
except ImportError:
    # keep backward compatibility
    def getCmd(instance, cmd):
        cmd = 'cmd_%s' % cmd
        if hasattr(instance, cmd):
            func = getattr(instance, cmd)
            return func
        return None

class CallvotePlugin(b3.plugin.Plugin):

    adminPlugin = None

    callvote = None
    callvotespecialmaplist = {}

    callvoteminlevel = {
        'capturelimit': 0, 'clientkick': 0, 'clientkickreason': 0, 'cyclemap': 0, 'exec': 0,
        'fraglimit': 0, 'kick': 0, 'map': 0, 'reload': 0, 'restart': 0, 'shuffleteams': 0,
        'swapteams': 0, 'timelimit': 0, 'g_bluewaverespawndelay': 0, 'g_bombdefusetime': 0,
        'g_bombexplodetime': 0, 'g_capturescoretime': 0, 'g_friendlyfire': 0, 'g_followstrict': 0,
        'g_gametype': 0, 'g_gear': 0, 'g_matchmode': 0, 'g_maxrounds': 0, 'g_nextmap': 0,
        'g_redwaverespawndelay': 0, 'g_respawndelay': 0, 'g_roundtime': 0, 'g_timeouts': 0,
        'g_timeoutlength': 0, 'g_swaproles': 0, 'g_waverespawns': 0}

    sql = {
        'q1': """INSERT INTO callvote VALUES (NULL, '%s', '%s', '%s', '%d', '%d', '%d', '%d')""",
        'q2': """SELECT c1.name, c2.* FROM callvote AS c2 INNER JOIN clients AS c1 ON c1.id = c2.client_id
                 ORDER BY time_add DESC LIMIT 0, 1""",
        'c1': """CREATE TABLE IF NOT EXISTS callvote (
                    id int(10) unsigned NOT NULL AUTO_INCREMENT,
                    client_id int(10) unsigned NOT NULL,
                    cv_type varchar(20) NOT NULL,
                    cv_data varchar(40) DEFAULT NULL,
                    max_num smallint(2) unsigned NOT NULL,
                    num_yes smallint(2) unsigned NOT NULL,
                    num_no smallint(2) unsigned NOT NULL,
                    time_add int(10) unsigned NOT NULL,
                    PRIMARY KEY (id),
                    KEY client_id (client_id)
                ) ENGINE=MyISAM  DEFAULT CHARSET=utf8 AUTO_INCREMENT=1;""",
        'c2': """CREATE TABLE IF NOT EXISTS callvote (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER(10) NOT NULL,
                    cv_type VARCHAR(20) NOT NULL,
                    cv_data VARCHAR(40) DEFAULT NULL,
                    max_num INTEGER(2) NOT NULL,
                    num_yes INTEGER(2) NOT NULL,
                    num_no INTEGER(2) NOT NULL,
                    time_add INTEGER(10) NOT NULL);"""
    }

    ####################################################################################################################
    ##                                                                                                                ##
    ##   STARTUP                                                                                                      ##
    ##                                                                                                                ##
    ####################################################################################################################

    def __init__(self, console, config=None):
        """
        Build the plugin object
        """
        b3.plugin.Plugin.__init__(self, console, config)
        if self.console.gameName != 'iourt42':
            self.critical("unsupported game : %s" % self.console.gameName)
            raise SystemExit(220)

        # get the admin plugin
        self.adminPlugin = self.console.getPlugin('admin')
        if not self.adminPlugin:
            self.critical('could not start without admin plugin')
            raise SystemExit(220)

    def onLoadConfig(self):
        """
        Load plugin configuration
        """
        try:

            for s in self.config.options('callvoteminlevel'):

                try:
                    self.callvoteminlevel[s] = self.console.getGroupLevel(self.config.get('callvoteminlevel', s))
                    self.debug('minimum required level for %s set to: %d' % (s, self.callvoteminlevel[s]))
                except KeyError, e:
                    self.error('invalid group level in callvoteminlevel/%s config value: %s' % (s, e))
                    self.debug('using default value (%s) for callvoteminlevel/%s' % (s, self.callvoteminlevel[s]))

        except NoSectionError:
            # all the callvote type can be issued by everyone
            self.warning('section "callvoteminlevel" missing in configuration file')

        try:

            for s in self.config.options('callvotespecialmaplist'):

                try:
                    s = s.lower()  # lowercase the map name
                    level = self.config.get('callvotespecialmaplist', s)
                    self.callvotespecialmaplist[s] = self.console.getGroupLevel(level)
                    self.debug('minimum required level to vote map %s set to: %d' % (s, self.callvotespecialmaplist[s]))
                except KeyError, e:
                    # can't load a default value here since the mapname is dynamic
                    self.error('invalid group level in callvotespecialmaplist/%s config value: %s' % (s, e))

        except NoSectionError:
            # all the maps can be voted by everyone
            self.warning('section "callvotespecialmaplist" missing in configuration file')

    def onStartup(self):
        """
        Initialize plugin settings
        """
        # create database tables if needed
        tables = self.console.storage.getTables()
        if not 'callvote' in tables:
            if self.console.storage.dsnDict['protocol'] == 'mysql':
                self.console.storage.query(self.sql['c1'])
            else:
                self.console.storage.query(self.sql['c2'])

        # register our commands
        if 'commands' in self.config.sections():
            for cmd in self.config.options('commands'):
                level = self.config.get('commands', cmd)
                sp = cmd.split('-')
                alias = None
                if len(sp) == 2:
                    cmd, alias = sp

                func = getCmd(self, cmd)
                if func:
                    self.adminPlugin.registerCommand(self, cmd, level, func, alias)

        try:
            self.registerEvent(self.console.getEventID('EVT_CLIENT_CALLVOTE'), self.onCallvote)
            self.registerEvent(self.console.getEventID('EVT_VOTE_PASSED'), self.onCallvoteFinish)
            self.registerEvent(self.console.getEventID('EVT_VOTE_FAILED'), self.onCallvoteFinish)
        except TypeError:
            self.registerEvent(self.console.getEventID('EVT_CLIENT_CALLVOTE'))
            self.registerEvent(self.console.getEventID('EVT_VOTE_PASSED'))
            self.registerEvent(self.console.getEventID('EVT_VOTE_FAILED'))

        # notice plugin started
        self.debug('plugin started')

    ####################################################################################################################
    ##                                                                                                                ##
    ##   EVENTS                                                                                                       ##
    ##                                                                                                                ##
    ####################################################################################################################

    def onEvent(self, event):
        """
        Old event system dispatcher
        """
        if event.type == self.console.getEventID('EVT_CLIENT_CALLVOTE'):
            self.onCallvote(event)
        elif event.type == self.console.getEventID('EVT_VOTE_PASSED'):
            self.onCallvoteFinish(event)
        elif event.type == self.console.getEventID('EVT_VOTE_FAILED'):
            self.onCallvoteFinish(event)

    def onCallvote(self, event):
        """
        Handle EVT_CLIENT_CALLVOTE
        """
        r = re.compile(r'''^(?P<type>\w+)\s?(?P<args>.*)$''')
        m = r.match(event.data)
        if not m:
            self.warning('could not parse callvote data: %s' % event.data)
            return

        self.callvote = {
            'client': event.client,
            'type': m.group('type').lower(),
            'args': m.group('args'),
            'time': self.getTime(),
            'max_num': 0,
        }

        for c in self.console.clients.getList():
            if c.team != b3.TEAM_SPEC:
                self.callvote['max_num'] += 1

        cl = self.callvote['client']
        tp = self.callvote['type']
        lv = self.callvoteminlevel[tp]

        # only perform checks on the current callvote if there is more
        # than 1 player being able to vote. If there is just 1 player in
        # non-spectator status, the vote will pass before we can actually
        # compute something on our side since there is a little bit of delay
        # between what is happening on the server and what is being parsed
        if not self.callvote['max_num'] > 1:
            self.debug('could not perform checks on [callvote %s]: not enough active players' % tp)
            return

        try:

            # checking required user level
            if cl.maxLevel < lv:
                self.veto()
                self.debug('aborting [callvote %s] command: no sufficient level for client <@%s>' % (tp, cl.id))
                cl.message('^7You can\'t issue this callvote. Required level: ^1%s' % self.getLevel(lv))
                return

            # checking required user level
            # for callvote map/nextmap to be higher
            # then the one specified in the config file
            if tp == 'map' or tp == 'g_nextmap':
                mapname = self.callvote['args'].lower()
                if mapname in self.callvotespecialmaplist.keys():
                    lv = self.callvotespecialmaplist[mapname]
                    if cl.maxLevel < lv:
                        self.veto()
                        self.debug('aborting [callvote %s] command: no sufficient level for client <@%s>' % (tp, cl.id))
                        cl.message('^7You can\'t issue this callvote. Required level: ^1%s' % self.getLevel(lv))
                        return

            # display the nextmap name if it's a g_nextmap/cyclemap callvote
            if tp == 'cyclemap' or tp == 'g_nextmap':
                mapname = self.console.getNextMap()
                if mapname:
                    self.console.say('^7Next Map: ^2%s' % mapname)

        except KeyError, e:
            # unhandled callvote type
            self.warning('could not handle [callvote %s] command: %s' % (tp, e))

    def onCallvoteFinish(self, event):
        """
        Handle the end of a callvote
        """
        if not self.callvote:
            self.debug('intercepted %s but there is no active callvote' % event.type.__str__())
            return

        # check again to see if it's the callvote we are actually holding
        r = re.compile(r'''^(?P<type>\w+)\s?(?P<args>.*)$''')
        m = r.match(event.data['what'])
        if not m:
            self.warning('could not parse %s data: %s' % (event.data, event.type.__str__()))
            self.veto()
            return

        if self.callvote['type'] != m.group('type') or self.callvote['args'] != m.group('args'):
            self.warning('intercepted %s but data doesn\'t match the currently stored callvote')
            self.veto()
            return

        # replace 'max_num' with the number of players connected,
        # no matter the team they belong to since they may have joined
        # RED or BLUE team to partecipate to the callvote
        self.callvote['num_no'] = event.data['no']
        self.callvote['num_yes'] = event.data['yes']
        self.callvote['max_num'] = len(self.console.clients.getList())

        try:
            # save the callvote in the storage
            self.console.storage.query(self.sql['q1'] % (self.callvote['client'].id, self.callvote['type'],
                                                         self.callvote['args'] if self.callvote['args'] else None,
                                                         self.callvote['max_num'], self.callvote['num_yes'],
                                                         self.callvote['num_no'], self.callvote['time']))
        except Exception, e:
            # something went wrong!
            self.error('could not store callvote: %s' % e)

    ####################################################################################################################
    ##                                                                                                                ##
    ##   OTHER METHODS                                                                                                ##
    ##                                                                                                                ##
    ####################################################################################################################

    @staticmethod
    def xStr(s):
        """
        Return a proper string representation of None
        if None is given, otherwise the given string
        """
        return 'N/A' if not s else s

    @staticmethod
    def getTimeString(tm):
        """
        Return a time string given it's value in seconds
        """
        if tm < 60:
            return '%d second%s' % (tm, 's' if tm > 1 else '')

        if 60 <= tm < 3600:
            tm = round(tm / 60)
            return '%d minute%s' % (tm, 's' if tm > 1 else '')

        tm = round(tm / 3600)
        return '%d hour%s' % (tm, 's' if tm > 1 else '')

    @staticmethod
    def getTime():
        """
        To ease automated tests
        """
        return time.time()

    def getLevel(self, level):
        """
        Return the group name associated to the given group level
        """
        mingroup = None
        groups = self.console.storage.getGroups()

        for x in groups:

            if x.level < level:
                continue

            if mingroup is None:
                mingroup = x
                continue

            if x.level < mingroup.level:
                mingroup = x

        return mingroup.name

    def veto(self):
        """
        Stop the current callvote
        """
        self.console.write('veto')
        self.callvote = None

    ####################################################################################################################
    ##                                                                                                                ##
    ##   COMMANDS                                                                                                     ##
    ##                                                                                                                ##
    ####################################################################################################################

    def cmd_veto(self, data, client, cmd=None):
        """
        Cancel the current callvote
        """
        self.veto()

    def cmd_lastvote(self, data, client, cmd=None):
        """
        Display informations about the last callvote
        """
        cursor = self.console.storage.query(self.sql['q2'])
        if cursor.EOF:
            cmd.sayLoudOrPM(client, '^7could not retrieve last callvote')
            cursor.close()
            return

        rw = cursor.getRow()
        tm = self.getTime() - int(rw['time_add'])
        m1 = '^7Last vote issued by ^3%s ^2%s ^7ago' % (rw['name'], self.getTimeString(tm))
        m2 = '^7Type: ^3%s ^7- Data: ^3%s' % (rw['cv_type'], self.xStr(rw['cv_data']))
        m3 = '^7Result: ^2%s^7:^1%s ^7on ^3%s ^7client%s' % (rw['num_yes'], rw['num_no'], rw['max_num'],
                                                             's' if int(rw['max_num']) > 1 else '')
        cursor.close()

        cmd.sayLoudOrPM(client, m1)
        cmd.sayLoudOrPM(client, m2)
        cmd.sayLoudOrPM(client, m3)