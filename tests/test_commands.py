#
# Jumper Plugin for BigBrotherBot(B3) (www.bigbrotherbot.net)
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

from b3 import TEAM_RED
from b3 import TEAM_BLUE
from b3 import TEAM_SPEC
from textwrap import dedent
from mockito import when
from callvote import CallvotePlugin
from tests import logging_disabled
from tests import CallvoteTestCase
from b3.config import CfgConfigParser


class Test_events(CallvoteTestCase):

    def setUp(self):

        CallvoteTestCase.setUp(self)

        with logging_disabled():
            from b3.fake import FakeClient

        # create some clients
        self.mike = FakeClient(console=self.console, name="Mike", guid="mikeguid", team=TEAM_RED,  groupBits=128)
        self.bill = FakeClient(console=self.console, name="Bill", guid="billguid", team=TEAM_BLUE, groupBits=16)
        self.mark = FakeClient(console=self.console, name="Mark", guid="markguid", team=TEAM_RED,  groupBits=2)
        self.sara = FakeClient(console=self.console, name="Sara", guid="saraguid", team=TEAM_SPEC, groupBits=1)

        self.conf = CfgConfigParser()
        self.p = CallvotePlugin(self.console, self.conf)

    def init(self, config_content=None):
        if config_content:
            self.conf.loadFromString(config_content)
        else:
            self.conf.loadFromString(dedent(r"""
                [callvoteminlevel]
                capturelimit: guest
                clientkick: guest
                clientkickreason: guest
                cyclemap: guest
                exec: guest
                fraglimit: guest
                kick: guest
                map: guest
                reload: guest
                restart: guest
                shuffleteams: guest
                swapteams: guest
                timelimit: guest
                g_bluewaverespawndelay: guest
                g_bombdefusetime: guest
                g_bombexplodetime: guest
                g_capturescoretime: guest
                g_friendlyfire: guest
                g_followstrict: guest
                g_gametype: guest
                g_gear: guest
                g_matchmode: guest
                g_maxrounds: guest
                g_nextmap: guest
                g_redwaverespawndelay: guest
                g_respawndelay: guest
                g_roundtime: guest
                g_timeouts: guest
                g_timeoutlength: guest
                g_swaproles: guest
                g_waverespawns: guest

                [callvotespecialmaplist]
                #ut4_abbey: guest
                #ut4_abbeyctf: guest

                [commands]
                lastvote: mod
                veto: mod
            """))

        self.p.onLoadConfig()
        self.p.onStartup()

        # return a fixed timestamp
        when(self.p).getTime().thenReturn(1399725576)

    def tearDown(self):
        self.mike.disconnects()
        self.bill.disconnects()
        self.mark.disconnects()
        self.sara.disconnects()
        CallvoteTestCase.tearDown(self)

    ####################################################################################################################
    ##                                                                                                                ##
    ##   TEST CASES                                                                                                   ##
    ##                                                                                                                ##
    ####################################################################################################################

    def test_cmd_veto(self):
        # GIVEN
        self.init()
        self.mike.connects("1")
        self.bill.connects("2")
        self.mark.connects("3")
        self.sara.connects("4")
        # WHEN
        self.console.parseLine('''Callvote: 4 - "map ut4_dressingroom"''')
        self.mike.says('!veto')
        # THEN
        self.assertIsNone(self.p.callvote)


    def test_cmd_lastvote_legit(self):
        # GIVEN
        self.init()
        self.mike.connects("1")
        self.bill.connects("2")
        self.mark.connects("3")
        self.sara.connects("4")
        # WHEN
        self.console.parseLine('''Callvote: 4 - "map ut4_casa"''')
        self.p.callvote['time'] = self.p.getTime() - 10  # fake timestamp
        self.console.parseLine('''VotePassed: 3 - 0 - "map ut4_casa"''')
        self.mike.clearMessageHistory()
        self.mike.says('!lastvote')
        # THEN
        self.assertIsNotNone(self.p.callvote)
        self.assertListEqual(["Last vote issued by Sara 10 seconds ago",
                              "Type: map - Data: ut4_casa",
                              "Result: 3:0 on 4 clients"], self.mike.message_history)