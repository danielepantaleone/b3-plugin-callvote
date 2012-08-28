# Callvote Plugin for BigBrotherBot
# Copyright (C) 2012 Mr.Click
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
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# CHANGELOG
#
# 27/08/2012 (v1.0 Mr.Click)
#  - initial version

__author__ = 'Mr.Click - http://www.goreclan.net'
__version__ = '1.0'

import b3
import b3.plugin
import b3.events
import string
from threading import Timer


class Callvote:
    client = None
    data = {'type' : None, 'time' : 0, 'data' : None}
    vote = {'yes': 0, 'no': 0, 'max' : 0}    

        
class CallvotePlugin(b3.plugin.Plugin):
    
    _adminPlugin = None
  
    _minLevelKick = 20
    _minLevelMap = 20
    _minLevelNextmap = 20
    _minLevelCyclemap = 20
    
    _callvote = None
    _timer = None
    
    _INSERT_DATA = "INSERT INTO `callvotelog` (`client_id`, `type`, `data`, `yes`, `no`, `time_add`) VALUES ('%s', '%s', '%s', '%d', '%d', '%d')"
    _INSERT_NO_DATA = "INSERT INTO `callvotelog` (`client_id`, `type`, `yes`, `no`, `time_add`) VALUES ('%s', '%s', '%d', '%d', '%d')"
    _SELECT_LAST = "SELECT `c1`.`name`, `c2`.* FROM  `callvotelog` AS `c2` INNER JOIN `clients` AS `c1` ON `c1`.`id` = `c2`.`client_id` ORDER BY  `time_add` DESC LIMIT 0 , 1"
    
    
    def onLoadConfig(self):
        """\
        Load the config
        """
        self.verbose('Loading config')
        
        try:
            self._minLevelKick = self.config.getint('minlevels', 'kick')
            self.debug('Callvote min level kick set to: %d.' % self._minLevelKick)
        except Exception, e:
            self.error('Error while reading min level kick configuration value: %s. Using default value: %d.' % (e, self._minLevelKick))
            pass
          
        try:
            self._minLevelMap = self.config.getint('minlevels', 'map')
            self.debug('Callvote min level map set to: %d.' % self._minLevelMap)
        except Exception, e:
            self.error('Error while reading min level map configuration value: %s. Using default value: %d.' % (e, self._minLevelMap))
            pass 
        
        try:
            self._minLevelNextmap = self.config.getint('minlevels', 'nextmap')
            self.debug('Callvote min level nextmap set to: %d.' % self._minLevelNextmap)
        except Exception, e:
            self.error('Error while reading min level nextmap configuration value: %s. Using default value: %d.' % (e, self._minLevelKick))
            pass
        
        try:
            self._minLevelCyclemap = self.config.getint('minlevels', 'kick')
            self.debug('Callvote min level cyclemap set to: %d.' % self._minLevelCyclemap)
        except Exception, e:
            self.error('Error while reading min level cyclemap configuration value: %s. Using default value: %d.' % (e, self._minLevelCyclemap))
            pass


    def onStartup(self):
        """\
        Initialize plugin settings
        """
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
                if len(sp) == 2: cmd, alias = sp

                func = self.getCmd(cmd)
                if func: self._adminPlugin.registerCommand(self, cmd, level, func, alias)
        
        # Register the events needed
        self.registerEvent(b3.events.EVT_GAME_WARMUP)
        self.registerEvent(b3.events.EVT_CLIENT_TEAM_CHANGE)
        self.registerEvent(b3.events.EVT_CLIENT_CALLVOTE)
        self.registerEvent(b3.events.EVT_CLIENT_VOTE)
        
        # Creating necessary variables inside the client object
        for c in self.console.clients.getList():
            c.setvar(self,'voted',False)
            
        # Checking for correct Urban Terror version
        try:
            gamename = self.consolegetCvar('gamename').getString()
            if gamename != 'q3urt42':
                self.error("Callvote logging is provided since Urban Terror 4.2. Disabling the plugin.")
                self.disable()
        except Exception, e:
            self.warning("Could not query server for gamename. Unable to check correct Urban Terror version. Disabling the plugin.", exc_info=e)
            self.disable()
    
    
    # ------------------------------------- Handle Events ------------------------------------- #        
        

    def onEvent(self, event):
        """\
        Handle intercepted events
        """
        if event.type == b3.events.EVT_GAME_WARMUP:
            self.onWarmup()
        if event.type == b3.events.EVT_CLIENT_TEAM_CHANGE:
            self.onTeamChange(event)
        if event.type == b3.events.EVT_CLIENT_CALLVOTE:
            self.onClientCallvote(event)                    
        if event.type == b3.events.EVT_CLIENT_VOTE:
            self.onClientVote(event)
                    
                
    # --------------------------------------- Functions --------------------------------------- #
        
          
    def getCmd(self, cmd):
        cmd = 'cmd_%s' % cmd
        if hasattr(self, cmd):
            func = getattr(self, cmd)
            return func
        return None    
        
    
    def reset(self):
        """\
        Reset voting variables
        """
        # Resetting client vars
        for c in self.console.clients.getList():
            c.setvar(self,'voted',False)
        
        # Clearing the Timer if any
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        
        # Removing a previously set Callvote object
        self._callvote = None
         
         
    def getHumanReadableTime(self, timestamp):
        """
        Return a string representing the Human Readable Time of the given timestamp
        """
        if timestamp < 60: 
            if timestamp == 1: return '%d second' % timestamp
            else: return '%d seconds' % timestamp
        elif timestamp >= 60 and timestamp < 3600:
            timestamp = round(timestamp/60)
            if timestamp == 1: return '%d minute' % timestamp
            else: return '%d minutes' % timestamp
        else:
            timestamp = round(timestamp/3600)
            if timestamp == 1: return '%d hour' % timestamp
            else: return '%d hours' % timestamp
            
            
    def getRequiredUserLevel(self, level):
        """
        Returns the group name required to issue the specified type of /callvote command
        """
        minGroup = None        
        groups = self.console.storage.getGroups()
        
        for x in groups:
            if x.level < level: continue
            if minGroup is not None:
                # Matching previously set minGroup
                if x.level < minGroup.level:
                    minGroup = x
            else:
                # First iteration
                minGroup = x
                
        return minGroup.name
        
    
    def getCallvote(self, event):
        """\
        Return a Callvote object from a given event
        """
        # Splitting the vote_string to get necessary data
        data = string.split(event.data['vote_string'],None,1)
        
        callvote = Callvote()
        callvote.client = event.client
        callvote.client.setvar(self,'voted',True)
        callvote.data['time'] = int(self.console.time())
        callvote.data['type'] = data[0]
        
        # Votes such as cyclemap don't carry any info in the vote_string
        if data[1]: callvote.data['data'] = data[1]
        
        # The player who issued the votation already voted F1
        # We need to track this in order to build a correct voting result
        # The assignment 'callvote.vote['no'] = 0' actually produce no effect, but still...    
        callvote.vote['yes'] = 1
        callvote.vote['no'] = 0
        
        # Computing the number of players that can actually vote
        # In Urban Terror voting from spectator mode is not allowed
        # so we have to discard players that are in b3.TEAM_SPEC team
        for c in self.console.clients.getList():
            if c.team != b3.TEAM_SPEC: 
                callvote.vote['max'] += 1
        
        return callvote
        
    
    def onClientCallvote(self, event):
        """\
        Handle client callvote
        """
        # Building a proper Callvote object
        self._callvote = self.getCallvote(event)
        
        # Since there is a bit of delay between a /callvote command being issued on the server
        # and the b3 generating the corresponding event, we probably are not able to control everything.
        # As an example think about this situation:
        #
        #    Bob  - Team Red
        #    Tom  - Team Spectator
        #    Lisa - Team Spectator
        #
        # If Bob issue a /callvote command, the votation will end as soon as the countdown starts
        # since he's the only one able to do /vote (spectators are excluded by the server engine 
        # and the player who issued the votation automatically voted F1 - go figure).
        #
        # At the current state what we can do is:
        #    
        #    - check how many players are able to issue a /vote command
        #    - if more than 1, perform all the controls we need, otherwise handle directly
        #      the end of the current votation, in order to avoid problems (timing related)
        
        if self._callvote.vote['max'] > 1:
            # We got some time to perform our checks on the current callvote
            if self._callvote.data['type'] == 'kick':
                self.verbose('Intercepted "/callvote kick <player>" command. Performing checks on the current callvote.')
                self.onClientCallvoteKick()
            elif self._callvote.data['type'] == 'map':
                self.verbose('Intercepted "/callvote map <mapname>" command. Performing checks on the current callvote.')
                self.onClientCallVoteMap()
            elif self._callvote.data['type'] == 'nextmap':
                self.verbose('Intercepted "/callvote nextmap <mapname>" command. Performing checks on the current callvote.')
                self.onClientCallVoteNextmap()
            elif self._callvote.data['type'] == 'cyclemap':
                self.verbose('Intercepted "/callvote cyclemap" command. Performing checks on the current callvote.')
                self.onClientCallVoteCyclemap()
            else:
                # This type of vote is not handled by the plugin yet. Simply do nothing
                self.debug('Intercepted unhandled type of client callvote: %s. Skipping...' % event.data['vote_string'])
                self._callvote = None
        else:
            # Directly handling the finish of the votation
            self.debug('Unable to perform callvote checks due to timing problems. Directly handling the end of the current votation: %s' % event.data['vote_string'])
            self.onCallvoteFinish()
        
            
    def onClientCallvoteKick(self):
        """\
        Handle /callvote kick <player>
        """
        # Checking sufficient level for this type of vote
        if self._callvote.client.maxLevel < self._minLevelKick:
            self.console.write('veto')
            self._callvote.client.message('^3You can\'t vote to kick players. Required level: ^1%s' % self.getRequiredUserLevel(self._minLevelKick))
            self.reset()
            return False
        
        # Searching the target client
        sclient = self._adminPlugin.findClientPrompt(self._callvote.data['data'])
        if not sclient:
            self.console.write('veto')
            self.debug('Invalid target client name specified in "/callvote kick <player>" command. Aborting...')
            self._callvote.client.message('^3You specified an invalid target. Client ^7%s ^3is not on the server.' % (self._callvote.data['data']))
            self.reset()
            return False
 
        # Checking higher level protection
        if self._callvote.client.maxLevel <= sclient.maxLevel:
            self.console.write('veto')
            self._callvote.client.message('^3%s is a higher level player. You can\'t vote to kick him' % sclient.name)
            self.reset()
            return False

        # The callvote is legit.
        # We can now start a countdown like the one started
        # by the Urban Terror server engine (more or less)
        self.debug('Completed check on "/callvote kick <player>" command. The callvote is legit. Starting the timer...')
        self._timer = Timer(30, self.onCallvoteFinish)
        self._timer.start()
        
    
    def onClientCallvoteMap(self):
        """\
        Handle /callvote map <mapname>
        """
        # Checking sufficient level for this type of vote
        if self._callvote.client.maxLevel < self._minLevelMap:
            self.console.write('veto')
            self._callvote.client.message('^3You can\'t vote to change map. Required level: ^1%s' % self.getRequiredUserLevel(self._minLevelMap))
            self.reset()
            return False
        
        # Checking if the specified map is loaded on the server
        # If the getMaps() function fails in providing the server map list
        # we are going to skip this check. The server engine will not load the map anyway.
        maps = self.console.getMaps()
        if maps is not None:
            if self._callvote.data['data'] not in maps:
                self.console.write('veto')
                self.debug('Invalid map specified in "/callvote map <mapname>" command. Aborting...')
                self._callvote.client.message('^3You specified an invalid map name. Map ^7%s ^3is not on the server.' % (self._callvote.data['data']))
                self.reset()
                return False
        
        # The callvote is legit.
        # We can now start a countdown like the one started
        # by the Urban Terror server engine (more or less)
        self.debug('Completed check on "/callvote map <mapname>" command. The callvote is legit. Starting the timer...')
        self._timer = Timer(30, self.onCallvoteFinish)
        self._timer.start()
        
      
    def onClientCallvoteNextmap(self):
        """\
        Handle /callvote nextmap <mapname>
        """
        # Checking sufficient level for this type of vote
        if self._callvote.client.maxLevel < self._minLevelNextmap:
            self.console.write('veto')
            self._callvote.client.message('^3You can\'t vote to change nextmap. Required level: ^1%s' % self.getRequiredUserLevel(self._minLevelNextmap))
            self.reset()
            return False
        
        # Checking if the specified map is loaded on the server
        # If the getMaps() function fails in providing the server map list
        # we are going to skip this check. The server engine will not load the map anyway.
        maps = self.console.getMaps()
        if maps is not None:
            if self._callvote.data['data'] not in maps:
                self.console.write('veto')
                self.debug('Invalid map specified in "/callvote nextmap <mapname>" command. Aborting...')
                self._callvote.client.message('^3You specified an invalid map name. Map ^7%s ^3is not on the server.' % (self._callvote.data['data']))
                self.reset()
                return False
        
        # The callvote is legit.
        # We can now start a countdown like the one started
        # by the Urban Terror server engine (more or less)
        self.debug('Completed check on "/callvote nextmap <mapname>" command. The callvote is legit. Starting the timer...')
        self._timer = Timer(30, self.onCallvoteFinish)
        self._timer.start()
        

    def onClientCallvoteCyclemap(self):
        """\
        Handle /callvote cyclemap
        """
        # Checking sufficient level for this type of vote
        if self._callvote.client.maxLevel < self._minLevelCyclemap:
            self.console.write('veto')
            self._callvote.client.message('^3You can\'t vote to cycle current map. Required level: ^1%s' % self.getRequiredUserLevel(self._minLevelCyclemap))
            self.reset()
            return False
        
        # The callvote is legit.
        # We can now start a countdown like the one started
        # by the Urban Terror server engine (more or less)
        self.debug('Completed check on "/callvote cyclemap" command. The callvote is legit. Starting the timer...')
        self._timer = Timer(30, self.onCallvoteFinish)
        self._timer.start()
        
    
    def onVote(self, event):
        """\
        Handle /vote <yes|no> commands
        """
        # Check if a Callvote object has been created
        # for the current votation in order to prevent failures
        if self._callvote is not None:
            if int(event.data['value']) == 1:
                self.verbose('Interceped "/vote yes" command. Handling the event.')
                self._callvote.vote['yes'] += 1
            elif int(event.data['value']) == 2:
                self.verbose('Interceped "/vote no" command. Handling the event.')
                self._callvote.vote['no'] += 1
                
            # Checking if we collected all the necessary /vote commands
            # If so we can cancel the timer and handle the end of the votation
            if self._callvote.vote['yes'] + self._callvote.vote['no'] == self._callvote.vote['max']:
                self.debug('Event Client Callvote ended prematurely. All the active players already voted.')
                self._timer.cancel()
                self._timer = None
                self.onVoteFinish()
                
    
    def onVoteFinish(self):
        """\
        Handle the end of a votation
        """
        # Check if the callvote object has been created
        # for the current votation in order to prevent failures
        if self._callvote is not None:
            # Storing the callvote in the database
            if self._callvote.data['data'] is not None:
                self.debug("Event Client Callvote finished [ type : %s | data : %s | result : (%d:%d) ]" % (self._callvote.data['type'], self._callvote.data['data'], self._callvote.vote['yes'], self._callvote.vote['no']))
                self.console.storage.query(self._INSERT_DATA % (self._callvote.client.id, self._callvote.data['type'], self._callvote.data['data'], self._callvote.vote['yes'], self._callvote.vote['no'], self._callvote.data['time']))
            else:
                self.debug("Event Client Callvote finished [ type : %s | result : (%d:%d) ]" % (self._callvote.data['type'], self._callvote.vote['yes'], self._callvote.vote['no']))
                self.console.storage.query(self._INSERT_NO_DATA % (self._callvote.client.id, self._callvote.data['type'], self._callvote.vote['yes'], self._callvote.vote['no'], self._callvote.data['time']))
            
            # Resetting voting variables
            # Ready to accept another /callvote
            self.reset()
                
                 
    def onTeamChange(self, event):
        """\
        Handle team changes events
        """
        # We need to adjust the maximum number of clients that can take part
        # to the current votation according to team change (spectators are excluded)
        if self._callvote is not None:
            if event.data != b3.TEAM_SPEC:
                if not event.client.isvar(self,'voted') or event.client.var(self,'voted').value == False:
                    self._callvote.vote['max'] += 1
            elif event.data == b3.TEAM_SPEC:
                if not event.client.isvar(self,'voted') or event.client.var(self,'voted').value == False:
                    self._callvote.vote['max'] += 1

        
    # --------------------------------------- Commands --------------------------------------- #
    
  
    def cmd_veto(self, data, client, cmd=None):
        """\
        Cancel the vote in progress
        """
        self.console.write('veto')
        self.reset()
       
    
    def cmd_lastvote(self, data, client, cmd=None):
        """\
        Displays informations about the last vote
        """
        cursor = self.console.storage.query(self._SELECT_LAST)
        if cursor.EOF:
            # No entries in the callvotelog table or missing join with
            # clients table. Can't do anything anyway..
            cmd.sayLoudOrPM(client, '^3Unable to retrieve last vote data')
            cursor.close()
            return False
        
        # Bulding the messages
        row = cursor.getRow()
        msg1 = '^3Last vote issued by ^4%s ^2%s ^3ago' % (row['name'], self.getHumanReadableTime(int(self.console.time())-int(row['time_add'])))
        msg2 = '^3Type: ^7%s' % (row['type'])
        
        # Adding callvote data (if any)
        if row['type'] == 'map' or row['type'] == 'nextmap': 
            msg2 += '^3 - Map: ^7%s' % row['data']
        elif row['type'] == 'kick': 
            msg2 += '^3 - Client: ^7%s' % row['data']
        
        # Adding callvote result
        if int(row['yes']) > int(row['no']) == 1: 
            msg2 += '^3 - Result: ^2passed'
        else:  
            msg2 += '^3 - Result: ^1failed'

        
        # Closing active cursor
        cursor.close()
        
        # Displaying messages
        cmd.sayLoudOrPM(client, msg1)
        cmd.sayLoudOrPM(client, msg2)
        
        