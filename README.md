Callvote Plugin for BigBrotherBot
=================================

## Description

This plugin provides advanced features related to the Urban Terror 4.2 callvotes.<br />
With this plugin is possible to specify which b3 group has access to specific callvotes.<br />
Since there is a bit of delay between a /callvote command being issued on the server and the b3 generating the corresponding event, is not possible to handle everything
As an example think about this situation:

    Bob  - Team Red
    Tom  - Team Spectator
    Lisa - Team Spectator
 
If Bob issue a /callvote command, the callvote will end as soon as the countdown starts since he's the only one able to do /vote. 
Because of this we will perform checks on a callvote being issued on the server just if there is more than 1 player being able to vote.

## How to install

### Installing the plugin

* Copy **callvote.py** into **b3/extplugins**
* Copy **plugin_callvote.ini** into **b3/extplugins/conf**
* Import **callvote.sql** into your b3 database
* Load the plugin in your **b3.xml** configuration file

### Requirements

* Urban Terror 4.2 server
* iourt42 parser (at least v1.18)

## In-game user guide

* **!lastvote** - *display the last callvote issued on the server*
* **!veto** - *cancel the current callvote*

## Support

For support regarding this very plugin you can find me on IRC on **#goreclan** @ **Quakenet**<br>
For support regarding Big Brother Bot you may ask for help on the official website: http://www.bigbrotherbot.net