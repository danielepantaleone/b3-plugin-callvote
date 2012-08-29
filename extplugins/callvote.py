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
# 28/08/2012 (v1.0 Mr.Click)
#  - initial version
#
# 29/08/2012 (v1.1 Mr.Click)
#  - plugin now handle also callvote for reload, restart and shuffleteams
#  - changed configuration handler => using multiple dictionaries instead of separate variables
#  - added new debug log messages
#  - added callvote spam protection
#  - code cleanup

__author__ = 'Mr.Click - http://www.goreclan.net'
__version__ = '1.1'

import b3
import b3.plugin
import b3.events
import string
from threading import Timer


class Callvote:
    client = None
    data = { 'type' : None, 'time' : 0, 'data' : None }
    vote = { 'yes': 0, 'no': 0, 'max' : 0 }    

        
class CallvotePlugin(b3.plugin.Plugin):
    
    _adminPlugin = None
  
    _callvoteMinLevel = { 'kick' : 20, 'map' : 20, 'nextmap' : 20, 'cyclemap' : 20, 'reload' : 20, 'restart' : 20, 'shuffleteams' : 20 }
    _callvoteWaitTime = { 'kick' : 60, 'map' : 60, 'nextmap' : 60, 'cyclemap' : 60, 'reload' : 60, 'restart' : 60, 'shuffleteams' : 60 }
    _lastCallvoteTime = { 'kick' :  0, 'map' :  0, 'nextmap' :  0, 'cyclemap' :  0, 'reload' :  0, 'restart' :  0, 'shuffleteams' :  0 }
        
    _callvote = None
    _countdown = None
    
    _INSERT_DATA = "INSERT INTO `callvotelog` (`client_id`, `type`, `data`, `yes`, `no`, `time_add`) VALUES ('%s', '%s', '%s', '%d', '%d', '%d')"
    _INSERT_NO_DATA = "INSERT INTO `callvotelog` (`client_id`, `type`, `yes`, `no`, `time_add`) VALUES ('%s', '%s', '%d', '%d', '%d')"
    _SELECT_LAST = "SELECT `c1`.`name`, `c2`.* FROM  `callvotelog` AS `c2` INNER JOIN `clients` AS `c1` ON `c1`.`id` = `c2`.`client_id` ORDER BY  `time_add` DESC LIMIT 0 , 1"
    
    
    def onLoadConfig(self):
        """\
        Load the config
        """
        self.verbose('Loading config')
        
        # Loading callvote minimum required levels
        for setting in self.config.get('callvoteMinLevel'):
            try:
                self._callvoteMinLevel[setting.get('name')] = int(setting.text)
                self.debug('Callvote min level %s set to: %d.' % (setting.get('name'), self._callvoteMinLevel[setting.get('name')]))
            except:
                self.error('Error while reading min level %s config value: %s. Using default value: %d.' % (setting.get('name'), e, self._callvoteMinLevel[setting.get('name')]))
                pass
            
        # Loading callvote spam protection settings
        for setting in self.config.get('callvoteWaitTime'):
            try:
                self._callvoteWaitTime[setting.get('name')] = int(setting.text)
                self.debug('Callvote %s wait time set to: %d.' % (setting.get('name'), self._callvoteWaitTime[setting.get('name')]))
            except:
                self.error('Error while reading callvote %s wait time config value: %s. Using default value: %d.' % (setting.get('name'), e, self._callvoteWaitTime[setting.get('name')]))
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
      
      
    def xStr(self,s):
        if s is None:
            return 'none'
        return s
    
    
    def reset(self):
        """\
        Reset voting variables
        """
        # Resetting client vars
        for c in self.console.clients.getList():
            c.setvar(self,'voted',False)
        
        # Clearing the Timer if any
        if self._countdown is not None:
            self._countdown.cancel()
            self._countdown = None
        
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
        
        # Votes such as cyclemap, reload, restart and shuffleteams 
        # don't carry any information in the vote_string
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
        
    
    def onWarmup(self):
        """\
        Handle game warmup
        """
        # Called on a new level.
        # If there was a votation on the previous map the serve engine will automatically discard it.
        # We are going to do the same by resetting all the callvote related variables
        self.reset()
        
        
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
            self.debug('Intercepted "/callvote %s" command. Performing checks on the current callvote.' % event.data['vote_string'])
            
            try:
            
                # Checking sufficient level for this type of vote
                if self._callvote.client.maxLevel < self._callvoteMinLevel[self._callvote.data['type']]:
                    self.console.write('veto')
                    self.debug('No sufficient level for client %s [@%s] performing "/callvote %s" command. Aborting votation.' % (self._callvote.client.name, self._callvote.client.id, event.data['vote_string']))
                    self._callvote.client.message('^3You can\'t call this type of vote. Required level: ^1%s' % self.getRequiredUserLevel(self._callvoteMinLevel[self._callvote.data['type']]))
                    self.reset()
                    return False
                
                # Checking vote spamming for this type of vote
                nextCallvoteTime = self._lastCallvoteTime[self._callvote.data['type']] + self._callvoteWaitTime[self._callvote.data['type']]
                if nextCallvoteTime > int(self.console.time()):
                    self.console.write('veto')
                    self.debug('Intercepted vote spamming on "/callvote %s" command. Aborting votation."' % event.data['vote_string'])
                    self._callvote.client.message('^3You need to wait ^7%s ^3to call this type of vote' % self.getHumanReadableTime(nextCallvoteTime - int(self.console.time())))
                    self.reset()
                    return False
                
                # Checking correct kick target (only for kick callvote)
                if self._callvote.data['type'] == 'kick':
                    sclient = self._adminPlugin.findClientPrompt(self._callvote.data['data'])
                    if not sclient:
                        self.console.write('veto')
                        self.debug('Invalid target client name specified in "/callvote %s" command. Aborting votation.' % event.data['vote_string'])
                        self._callvote.client.message('^3You specified an invalid target. Client ^7%s ^3is not on the server' % (self._callvote.data['data']))
                        self.reset()
                        return False
                
                # Checking correct map name (only for map and nextmap callvote)
                if self._callvote.data['type'] == 'map' or self._callvote.data['type'] == 'nextmap':
                    maps = self.console.getMaps()
                    if maps is not None:
                        if self._callvote.data['data'] not in maps:
                            self.console.write('veto')
                            self.debug('Invalid map specified in "/callvote %s" command. Aborting votation.' % event.data['vote_string'])
                            self._callvote.client.message('^3You specified an invalid map name. Map ^7%s ^3is not on the server' % (self._callvote.data['data']))
                            self.reset()
                            return False
                
                # If we got here means that the callvote is legit.
                # We can now start a countdown like the one started by the Urban Terror server engine (more or less).
                self.debug('Completed check on "/callvote %s" command. The callvote is legit. Starting the timer.' % event.data['vote_string'])
                self._countdown = Timer(30, self.onCallvoteFinish)
                self._countdown.start()
                
            except KeyError, e:
                # This type of vote is not handled by the plugin yet. Simply do nothing.
                self.debug('Intercepted unhandled type of callvote command: /callvote %s. Discaring.' % event.data['vote_string'])
                self.reset()
                return False
           
        else:
            # Directly handling the finish of the votation.
            self.debug('Unable to perform callvote checks. Directly handling the end of the current votation: %s' % event.data['vote_string'])
            self.onCallvoteFinish()
        
          
    def onVote(self, event):
        """\
        Handle client vote
        """
        # Checking if we really are in a votation.
        if self._callvote is not None:
            self.debug('Interceped "/vote %s" command. Handling the event.' % event.data['value'])
            if int(event.data['value']) == 1:
                self._callvote.vote['yes'] += 1
            elif int(event.data['value']) == 2:
                self._callvote.vote['no'] += 1

            # Checking if we collected all the necessary /vote commands for the current votation.
            # If so we can cancel the timer and immediatly handle the end of the votation.
            if self._callvote.vote['yes'] + self._callvote.vote['no'] >= self._callvote.vote['max']:
                self.debug('Event client callvote ended prematurely. All the active players already voted.')
                self._countdown.cancel()
                self._countdown = None
                self.onVoteFinish()
                
    
    def onVoteFinish(self):
        """\
        Handle the end of a votation
        """
        # Checking if we really are in a votation.
        if self._callvote is not None:
            # Storing the callvote in the database
            if self._callvote.data['data'] is not None:
                self.debug("Event client callvote finished [ type : %s | data : %s | result : (%d:%d) ]" % (self._callvote.data['type'], self._callvote.data['data'], self._callvote.vote['yes'], self._callvote.vote['no']))
                self.console.storage.query(self._INSERT_DATA % (self._callvote.client.id, self._callvote.data['type'], self._callvote.data['data'], self._callvote.vote['yes'], self._callvote.vote['no'], self._callvote.data['time']))
            else:
                self.debug("Event client callvote finished [ type : %s | result : (%d:%d) ]" % (self._callvote.data['type'], self._callvote.vote['yes'], self._callvote.vote['no']))
                self.console.storage.query(self._INSERT_NO_DATA % (self._callvote.client.id, self._callvote.data['type'], self._callvote.vote['yes'], self._callvote.vote['no'], self._callvote.data['time']))
        
        # No need to put this in the if clause.
        # We are going to reset everything anyway...    
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
                    self._callvote.vote['max'] -= 1

        
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
        msg2 = '^3Type: ^7%s ^3- Data: ^7%s ^3- Result: ^2%s^7:^1%s' % (row['type'], self.xStr(row['data']), row['yes'], row['no'])
        cursor.close()
        
        # Displaying messages
        cmd.sayLoudOrPM(client, msg1)
        cmd.sayLoudOrPM(client, msg2)
        