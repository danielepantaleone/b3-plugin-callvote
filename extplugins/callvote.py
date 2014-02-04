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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

__author__ = 'Fenix'
__version__ = '1.8'

import b3
import b3.plugin
import b3.events
import re


class CallvotePlugin(b3.plugin.Plugin):

    _adminPlugin = None

    _callvote = dict()
    _callvote_special_maplist = dict()

    _callvote_min_level = {
        'capturelimit': 0, 'clientkick': 0, 'clientkickreason': 0, 'cyclemap': 0, 'exec': 0,
        'fraglimit': 0, 'kick': 0, 'map': 0, 'reload': 0, 'restart': 0, 'shuffleteams': 0,
        'swapteams': 0, 'timelimit': 0, 'g_bluewaverespawndelay': 0, 'g_bombdefusetime': 0,
        'g_bombexplodetime': 0, 'g_capturescoretime': 0, 'g_friendlyfire': 0, 'g_followstrict': 0,
        'g_gametype': 0, 'g_gear': 0, 'g_matchmode': 0, 'g_maxrounds': 0, 'g_nextmap': 0,
        'g_redwaverespawndelay': 0, 'g_respawndelay': 0, 'g_roundtime': 0, 'g_timeouts': 0,
        'g_timeoutlength': 0, 'g_swaproles': 0, 'g_waverespawns': 0}

    _sql = dict(
        q1="""INSERT INTO `callvote` VALUES (NULL, '%s', '%s', '%s', '%d', '%d', '%d', '%d')""",
        q2="""SELECT `c1`.`name`,
                     `c2`.*
                     FROM  `callvote` AS `c2`
                     INNER JOIN `clients` AS `c1`
                     ON `c1`.`id` = `c2`.`client_id`
                     ORDER BY `time_add` DESC
                     LIMIT 0 , 1""")

    ####################################################################################################################
    ##                                                                                                                ##
    ##   STARTUP                                                                                                      ##
    ##                                                                                                                ##
    ####################################################################################################################

    def __init__(self, console, config=None):
        """\
        Build the plugin object
        """
        b3.plugin.Plugin.__init__(self, console, config)
        if self.console.gameName != 'iourt42':
            self.critical("unsupported game : %s" % self.console.gameName)
            raise SystemExit(220)

    def onLoadConfig(self):
        """\
        Load plugin configuration
        """
        for s in self.config.options('callvoteminlevel'):

            try:
                self._callvote_min_level[s] = self.console.getGroupLevel(self.config.get('callvoteminlevel', s))
                self.debug('minimum required level for %s set to: %d' % (s, self._callvote_min_level[s]))
            except KeyError, e:
                self.error('invalid group level in settings/%s config value: %s' % (s, e))
                self.debug('using default value (%s) for settings/%s' % (s, self._callvote_min_level[s]))

        for s in self.config.options('callvotespecialmaplist'):

            try:
                s = s.lower()  # lowercase the map name to avoid false positives
                self._callvote_special_maplist[s] = self.console.getGroupLevel(self.config.get('callvotespecialmaplist', s))
                self.debug('minimum required level to vote map %s set to: %d' % (s, self._callvote_special_maplist[s]))
            except KeyError, e:
                # can't load a default value here since the mapname is dynamic
                self.error('invalid group level in settings/%s config value: %s' % (s, e))

    def onStartup(self):
        """\
        Initialize plugin settings
        """
        # get the admin plugin
        self._adminPlugin = self.console.getPlugin('admin')
        if not self._adminPlugin:
            self.error('could not find admin plugin')
            return False

        # register our commands
        if 'commands' in self.config.sections():
            for cmd in self.config.options('commands'):
                level = self.config.get('commands', cmd)
                sp = cmd.split('-')
                alias = None
                if len(sp) == 2:
                    cmd, alias = sp

                func = self.getCmd(cmd)
                if func:
                    self._adminPlugin.registerCommand(self, cmd, level, func, alias)

        # register the events needed
        self.registerEvent(b3.events.EVT_CLIENT_CALLVOTE, self.onCallvote)
        self.registerEvent(b3.events.EVT_VOTE_PASSED, self.onCallvoteFinish)
        self.registerEvent(b3.events.EVT_VOTE_FAILED, self.onCallvoteFinish)

        # notice plugin started
        self.debug('plugin started')

    ####################################################################################################################
    ##                                                                                                                ##
    ##   EVENTS                                                                                                       ##
    ##                                                                                                                ##
    ####################################################################################################################

    def onCallvote(self, event):
        """\
        Handle EVT_CLIENT_CALLVOTE
        """
        r = re.compile(r'''^(?P<type>\w+)\s?(?P<args>.*)$''')
        m = r.match(event.data)
        if not m:
            self.warning('could not parse callvote data: %s' % event.data)
            return

        self._callvote = dict()
        self._callvote['client'] = event.client
        self._callvote['type'] = m.group('type').lower()
        self._callvote['args'] = m.group('args')
        self._callvote['time'] = self.console.time()
        self._callvote['max_num'] = 0

        for c in self.console.clients.getList():
            if c.team != b3.TEAM_SPEC:
                self._callvote['max_num'] += 1

        # only perform checks on the current callvote if there is more
        # than 1 player being able to vote. If there is just 1 player in
        # non-spectator status, the vote will pass before we can actually
        # compute something on our side since there is a little bit of delay
        # between what is happening on the server and what is being parsed

        if not self._callvote['max_num'] > 1:
            return

        cl = self._callvote['client']
        tp = self._callvote['type']
        lv = self._callvote_min_level[tp]

        try:

            # checking required user level
            if cl.maxLevel < lv:
                self.console.write('veto')
                self.debug('aborting [callvote %s] command: no sufficient level for client [@%s]' % (tp, cl.id))
                cl.message('^7You can\'t call this vote. Required level: ^1%s' % self.getLevel(lv))
                return

            # checking required user level
            # for callvote map/nextmap to be higher
            # then the one specified in the config file
            if tp == 'map' or tp == 'g_nextmap':
                mapname = self._callvote['args'].lower()
                if mapname in self._callvote_special_maplist.keys():
                    lv = self._callvote_special_maplist[mapname]
                    if cl.maxLevel < lv:
                        self.console.write('veto')
                        self.debug('aborting [callvote %s] command: no sufficient level for client [@%s]' % (tp, cl.id))
                        cl.message('^7You can\'t call this vote. Required level: ^1%s' % self.getLevel(lv))
                        return

            # display the nextmap name if it's a g_nextmap/cyclemap callvote
            if tp == 'cyclemap' or tp == 'g_nextmap':
                mapname = self.console.getNextMap()
                if mapname:
                    self.console.say('^7Next Map: ^2%s' % mapname)

        except KeyError, e:
            # this type of callvote is not handled by the plugin
            self.error('could not handle [callvote %s] command: %s' % (tp, e))

    def onCallvoteFinish(self, event):
        """\
        Handle the end of a callvote
        """
        self._callvote['max_num'] = 0
        self._callvote['num_yes'] = event.data['yes']
        self._callvote['num_no'] = event.data['no']

        # calculate this again since someone may have joined
        # the game meanwhile the callvote was running
        for c in self.console.clients.getList():
            if c.team != b3.TEAM_SPEC:
                self._callvote['max_num'] += 1

        try:
            self.console.storage.query(self._sql['q1'] % (self._callvote['client'].id, self._callvote['type'],
                                                          self._callvote['args'] if self._callvote['args'] else None,
                                                          self._callvote['max_num'], self._callvote['num_yes'],
                                                          self._callvote['num_no'], self._callvote['time']))
        except KeyError, e:
            # something went wrong!
            self.error('could not store callvote: %s' % e)

    ####################################################################################################################
    ##                                                                                                                ##
    ##   FUNCTIONS                                                                                                    ##
    ##                                                                                                                ##
    ####################################################################################################################

    def getCmd(self, cmd):
        cmd = 'cmd_%s' % cmd
        if hasattr(self, cmd):
            func = getattr(self, cmd)
            return func
        return None

    def xStr(self, s):
        """\
        Return a proper string representation of None
        if None is given, otherwise the given string
        """
        return 'N/A' if not s else s

    def getTimeString(self, time):
        """\
        Return a time string given it's value in seconds
        """
        if time < 60:
            return '%d second%s' % (time, 's' if time > 1 else '')

        if 60 <= time < 3600:
            time = round(time / 60)
            return '%d minute%s' % (time, 's' if time > 1 else '')

        time = round(time / 3600)
        return '%d hour%s' % (time, 's' if time > 1 else '')

    def getLevel(self, level):
        """\
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

    ####################################################################################################################
    ##                                                                                                                ##
    ##   COMMANDS                                                                                                     ##
    ##                                                                                                                ##
    ####################################################################################################################

    def cmd_veto(self, data, client, cmd=None):
        """\
        Cancel the current callvote
        """
        self.console.write('veto')

    def cmd_lastvote(self, data, client, cmd=None):
        """\
        Display informations about the last callvote
        """
        cursor = self.console.storage.query(self._sql['q2'])
        if cursor.EOF:
            cmd.sayLoudOrPM(client, '^7Could not retrieve last callvote')
            cursor.close()
            return

        rw = cursor.getRow()
        tm = self.console.time() - int(rw['time_add'])
        m1 = '^7Last vote issued by ^3%s ^2%s ^7ago' % (rw['name'], self.getTimeString(tm))
        m2 = '^7Type: ^3%s ^7- Data: ^3%s' % (rw['cv_type'], self.xStr(rw['cv_data']))
        m3 = '^7Result: ^2%s^7:^1%s ^7on ^3%s ^7client%s' % (rw['num_yes'], rw['num_no'], rw['max_num'],
                                                             's' if int(rw['max_num']) > 1 else '')
        cursor.close()

        cmd.sayLoudOrPM(client, m1)
        cmd.sayLoudOrPM(client, m2)
        cmd.sayLoudOrPM(client, m3)