Callvote Plugin for BigBrotherBot [![BigBrotherBot](http://i.imgur.com/7sljo4G.png)][B3]
=================================

Description
-----------

A [BigBrotherBot][B3] plugin which provides advanced features related to the Urban Terror 4.2 callvotes.
With this plugin is possible to specify which B3 group has access to specific callvotes.
Moreover there is the possibility to specify a *special maps list* so that only a certain group of users can
issue callvote for map/nextmap if the level is in the *special maps list*.
Since there is a bit of delay between a /callvote command being issued on the server and the b3 generating the
corresponding event, is not possible to handle everything.
As an example think about this situation:

    Bob  - Team Red
    Tom  - Team Spectator
    Lisa - Team Spectator
 
If Bob issue a **/callvote** command, the callvote will end as soon as the countdown starts since he's the only
active player. Because of this we will perform checks on a callvote being issued on the server just if there is
more than 1 player being able to vote.

******
*NOTE: since B3 v1.10.1 beta this plugin has been included in the standard plugins set, thus all patches and updates will be performed in the official B3 repository.*
******

Download
--------

Latest version available [here](https://github.com/danielepantaleone/b3-plugin-callvote/archive/master.zip).

Installation
------------

* copy the `callvote.py` file into `b3/extplugins`
* copy the `plugin_callvote.ini` file in `b3/extplugins/conf`
* add to the `plugins` section of your `b3.xml` config file:

  ```xml
  <plugin name="callvote" config="@b3/extplugins/conf/plugin_callvote.ini" />
  ```
Requirements
------------

* Urban Terror 4.2 server [g_modversion >= 4.2.015]
* B3 [version >= 1.10dev]

In-game user guide
------------------

* **!lastvote** - `display the last callvote issued on the server`
* **!veto** - `cancel the current callvote`

Support
-------

If you have found a bug or have a suggestion for this plugin, please report it on the [B3 forums][Support].

[B3]: http://www.bigbrotherbot.net/ "BigBrotherBot (B3)"
[Support]: http://forum.bigbrotherbot.net/plugins-by-fenix/callvote-plugin/ "Support topic on the B3 forums"

[![Build Status](https://travis-ci.org/danielepantaleone/b3-plugin-callvote.svg?branch=master)](https://travis-ci.org/danielepantaleone/b3-plugin-callvote)
