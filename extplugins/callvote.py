#
# Callvote Plugin for BigBrotherBot(B3) (www.bigbrotherbot.net)
# Copyright (C) 2013 Fenix <fenix@urbanterror.info)
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

__author__ = 'Fenix - http://www.urbanterror.info'
__version__ = '1.2.1'

import b3
import b3.plugin
import b3.events
from threading import Timer

class Callvote:

    client = None

    cv_type = None
    cv_data = None
    
    max_num = 0
    num_yes = 0
    num_no = 0
    
    time_add = 0
    
    
    def __init__(self, client, cv_type, time_add):
        """
        Build the callvote object
        """
        self.client = client
        self.cv_type = cv_type
        self.time_add = time_add
        self.num_yes = 1
        
        # Set the vote flag for future use
        self.client.setvar(self,'voted', True)
        
        
class CallvotePlugin(b3.plugin.Plugin):
    
    _adminPlugin = None
    
    _callvote = None
    _callvoteTimer = None
    _callvoteMinLevel = { 'capturelimit' : 0,
                          'clientkick' : 0,
                          'clientkickreason' : 0,
                          'cyclemap' : 0,
                          'exec' : 0,
                          'fraglimit' : 0,
                          'kick' : 0,
                          'map' : 0,
                          'reload' : 0,
                          'restart' : 0,
                          'shuffleteams' : 0,
                          'swapteams' : 0,
                          'timelimit' : 0, 
                          'g_bluewaverespawndelay' : 0,
                          'g_bombdefusetime' : 0,
                          'g_bombexplodetime' : 0,
                          'g_capturescoretime' : 0,
                          'g_friendlyfire' : 0,
                          'g_followstrict' : 0,
                          'g_gametype' : 0,
                          'g_gear' : 0,
                          'g_matchmode' : 0,
                          'g_maxrounds' : 0,
                          'g_nextmap' : 0,
                          'g_redwaverespawndelay' : 0,
                          'g_respawndelay' : 0,
                          'g_roundtime' : 0,
                          'g_timeouts' : 0,
                          'g_timeoutlength' : 0,
                          'g_swaproles' : 0,
                          'g_waverespawns' : 0 }
    
    _team_gametype = ('tdm', 'ts', 'ftl', 'cah', 'ctf', 'bm')
    
    _sql = { 'q1' : "INSERT INTO `callvote` (`client_id`, `cv_type`, `cv_data`, `max_num`, `num_yes`, `num_no`, `time_add`) VALUES ('%s', '%s', '%s', '%d', '%d', '%d', '%d')",
             'q2' : "SELECT `c1`.`name`, `c2`.* FROM  `callvote` AS `c2` INNER JOIN `clients` AS `c1` ON `c1`.`id` = `c2`.`client_id` ORDER BY `time_add` DESC LIMIT 0 , 1", }
    
    
    def __init__(self, console, config=None):
        """
        Build the plugin object
        """
        b3.plugin.Plugin.__init__(self, console, config)
        if self.console.gameName != 'iourt42':
            self.critical("unsupported game : %s" % self.console.gameName)
            raise SystemExit(220)


    def onLoadConfig(self):
        """
        Load plugin configuration
        """
        self.verbose('Loading configuration file...')
        
        for s in self.config.options('callvoteminlevel'):
            
            try:
                self._callvoteMinLevel[s] = self.config.getint('callvoteminlevel', s)
                self.debug('Minimum required level for \'%s\' set to: %d' % (s, self._callvoteMinLevel[s]))
            except Exception, e:
                self.error('Unable to load minimum required level for \'%s\': %s' % (s, e))
                self.debug('Using default minimum required level for \'%s\': %d' % (s, self._callvoteMinLevel[s]))
                 
                 
    def onStartup(self):
        """
        Initialize plugin settings
        """
        # Get the admin plugin
        self._adminPlugin = self.console.getPlugin('admin')
        if not self._adminPlugin:    
            self.error('Could not find admin plugin')
            return False
        
        # Register our commands
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
        
        # Register the events needed
        self.registerEvent(b3.events.EVT_GAME_WARMUP)
        self.registerEvent(b3.events.EVT_GAME_ROUND_START)
        self.registerEvent(b3.events.EVT_CLIENT_TEAM_CHANGE)
        self.registerEvent(b3.events.EVT_CLIENT_CALLVOTE)
        self.registerEvent(b3.events.EVT_CLIENT_VOTE)
    
    
    # ######################################################################################### #
    # ##################################### HANDLE EVENTS ##################################### #        
    # ######################################################################################### #        
        

    def onEvent(self, event):
        """\
        Handle intercepted events
        """
        if event.type == b3.events.EVT_GAME_WARMUP:
            
            # In a team based gametype we have warmup flagging the map start,
            # so we'll use this event to clear a previous callvote. Using
            # EVT_GAME_ROUND_START is not correct since in a survivor gametype
            # like TS and BOMB we have multiple round start in the same map
            if self.console.game.gameType in self._team_gametype:
                self.reset()
        
        elif event.type == b3.events.EVT_GAME_ROUND_START:
          
            # In a non team based gametype we do not have warmup but just round
            # start, so we'll use this event to clear a previous callvote
            if self.console.game.gameType not in self._team_gametype:
                self.reset()
                    
        elif event.type == b3.events.EVT_CLIENT_TEAM_CHANGE:
            self.onTeamChange(event)
        elif event.type == b3.events.EVT_CLIENT_CALLVOTE:
            self.onCallvote(event)                    
        elif event.type == b3.events.EVT_CLIENT_VOTE:
            self.onVote(event)
                    
                
    # ######################################################################################### #
    # ####################################### FUNCTIONS ####################################### #        
    # ######################################################################################### #
        
          
    def getCmd(self, cmd):
        cmd = 'cmd_%s' % cmd
        if hasattr(self, cmd):
            func = getattr(self, cmd)
            return func
        return None    
      
      
    def xStr(self,s):
        if s is None:
            return 'N/A'
        return s
    
    
    def reset(self):
        """\
        Reset voting variables
        """
        for c in self.console.clients.getList():
            c.setvar(self,'voted',False)
        
        if self._callvoteTimer is not None:
            self._callvoteTimer.cancel()
            self._callvoteTimer = None
        
        self._callvote = None
        

    def getTimeString(self, time):
        """
        Return a time string given it's value in seconds
        """
        if time < 60:
            return '%d second%s' % (time, 's' if time > 1 else '')

        if time >= 60 and time < 3600:
            time = round(time/60)
            return '%d minute%s' % (time, 's' if time > 1 else '')

        time = round(time/3600)
        return '%d hour%s' % (time, 's' if time > 1 else '')
            
            
    def getLevel(self, level):
        """
        Return the group name associated to the given group level
        """
        minGroup = None        
        groups = self.console.storage.getGroups()
        
        for x in groups:
            
            if x.level < level: 
                continue
            
            if minGroup is None:
                minGroup = x
                continue

            if x.level < minGroup.level:
                minGroup = x
                
        return minGroup.name
        
    
    def getCallvote(self, event):
        """\
        Return a Callvote object from a given event
        """        
        data = event.data.split(None, 1)
        callvote = Callvote(event.client, data[0].lower(), self.console.time())

        if data[1]: 
            # Store extra data if any
            callvote.cv_data = data[1]

        for c in self.console.clients.getList():
            if c.team != b3.TEAM_SPEC: 
                callvote.max_num += 1
        
        return callvote
        
        
    def onCallvote(self, event):
        """\
        Handle EVT_CLIENT_CALLVOTE
        """
        # Building a proper Callvote object
        self._callvote = self.getCallvote(event)
        
        # Only perform checks on the current callvote if there is more
        # than 1 player being able to vote. If there is just 1 player in 
        # non-spectator status, the vote will pass before we can actually 
        # compute something on our side since there is a little bit of delay
        # between what is happening on the server and what is being parsed
        
        if self._callvote.max_num <= 1:
            self.onCallvoteEnd()
            
        try:
            
            client = self._callvote.client
            
            # Checking required user level for the current callvote
            if client.maxLevel < self._callvoteMinLevel[self._callvote.cv_type]:
                self.console.write('veto')
                self.debug('Aborting \'/callvote %s\' command. No sufficient level for client [@%s]' % (event.data, client.id))
                client.message('^7You can\'t call this vote. Required level: ^1%s' % self.getLevel(self._callvoteMinLevel[self._callvote.cv_type]))
                self.reset()
                return
            
            # Displaying the nextmap name if it's a g_nextmap/cyclemap callvote
            if self._callvote.cv_type == 'cyclemap' or self._callvote.cv_type == 'g_nextmap':
                mapname = self.console.getNextMap()
                if mapname: 
                    self.console.say('^7Next Map: ^2%s' % mapname)
            
            self._callvoteTimer = Timer(30, self.onCallvoteEnd)
            self._callvoteTimer.start()
            
        except KeyError:
            
            self.warning('Intercepted unhandled type of callvote command: /callvote %s' % event.data)
            self.reset()
           
          
    def onVote(self, event):
        """
        Handle EVT_CLIENT_VOTE
        """
        if self._callvote is not None:
            
            if event.data['value'] == '1':
                self._callvote.num_yes += 1
            elif event.data['value'] == '2':
                self._callvote.num_no += 1

            if self._callvote.num_yes + self._callvote.num_no >= self._callvote.max_num:
                self.debug('Event client callvote finished. All the active players voted')
                self._callvoteTimer.cancel()
                self._callvoteTimer = None
                self.onCallvoteEnd()
                
    
    def onCallvoteEnd(self):
        """\
        Handle the end of a callvote
        """
        if self._callvote is not None:
            
            self.console.storage.query(self._sql['q1'] % (self._callvote.client.id, 
                                                          self._callvote.cv_type, 
                                                          self._callvote.cv_data, 
                                                          self._callvote.max_num,
                                                          self._callvote.num_yes, 
                                                          self._callvote.num_no, 
                                                          self._callvote.time_add))
            
            self.debug("Stored new callvote [ cv_type : %s | cv_data : %s | max_num : %d | num_yes: %d | num_no : %d ]" % (self._callvote.cv_type, 
                                                                                                                           self.xStr(self._callvote.cv_data), 
                                                                                                                           self._callvote.max_num,
                                                                                                                           self._callvote.num_yes, 
                                                                                                                           self._callvote.num_no))
        
        self.reset()
                
                 
    def onTeamChange(self, event):
        """\
        Handle EVT_CLIENT_TEAM_CHANGE
        """
        if self._callvote is not None:
            if event.data != b3.TEAM_SPEC:
                if not event.client.var(self,'voted').value:
                    self._callvote.max_num += 1
            elif event.data == b3.TEAM_SPEC:
                if not event.client.var(self,'voted').value:
                    self._callvote.max_num -= 1

        
    # ######################################################################################### #
    # ######################################## COMMANDS ####################################### #        
    # ######################################################################################### # 

  
    def cmd_veto(self, data, client, cmd=None):
        """\
        Cancel the current callvote
        """
        self.console.write('veto')
        self.reset()
       
    
    def cmd_lastvote(self, data, client, cmd=None):
        """\
        Display informations about the last callvote
        """
        cursor = self.console.storage.query(self._sql['q2'])
        if cursor.EOF:
            cmd.sayLoudOrPM(client, '^7Could not retrieve last callvote')
            cursor.close()
            return
        
        row = cursor.getRow()
        msg1 = '^7Last vote issued by ^4%s ^2%s ^7ago' % (row['name'], self.getTimeString(self.console.time() - int(row['time_add'])))
        msg2 = '^7Type: ^3%s ^7- Data: ^3%s ^7- [^2%s^7:^1%s^7]' % (row['cv_type'], self.xStr(row['cv_data']), row['num_yes'], row['num_no'])
        
        cursor.close()
        
        cmd.sayLoudOrPM(client, msg1)
        cmd.sayLoudOrPM(client, msg2)
        