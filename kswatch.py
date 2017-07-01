#!/usr/bin/env python

# Copyright 2013, Timur Tabi
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# This software is provided by the copyright holders and contributors "as is"
# and any express or implied warranties, including, but not limited to, the
# implied warranties of merchantability and fitness for a particular purpose
# are disclaimed. In no event shall the copyright holder or contributors be
# liable for any direct, indirect, incidental, special, exemplary, or
# consequential damages (including, but not limited to, procurement of
# substitute goods or services; loss of use, data, or profits; or business
# interruption) however caused and on any theory of liability, whether in
# contract, strict liability, or tort (including negligence or otherwise)
# arising in any way out of the use of this software, even if advised of
# the possibility of such damage.

import sys
import os
import time
import urllib2
import HTMLParser
from subprocess import call
from optparse import OptionParser

# Parse the pledge HTML page
#
# It looks like this:
#
# <li class="reward shipping" ...>
# <input alt="$75.00" ... title="$75.00" />
# ...
# </li>
#
# So we need to scan the HTML looking for <li> tags with the proper class,
# (the class is the status of that pledge level), and then remember that
# status as we parse inside the <li> block.  The <input> tag contains a title
# with the pledge amount.  We return a list of tuples that include the pledge
# level, the reward ID, and a description
#
# The 'rewards' dictionary uses the reward value as a key, and
# (status, remaining) as the value.
class KickstarterHTMLParser(HTMLParser.HTMLParser):
    def __init__(self):
        HTMLParser.HTMLParser.__init__(self)
        self.in_li_block = False    # True == we're inside an <li class='...'> block
        self.in_desc_block = False # True == we're inside a <p class="description short"> block

    def process(self, url) :
        while True:
            try:
                f = urllib2.urlopen(url)
                break
            except urllib2.HTTPError as e:
                print 'HTTP Error', e
            except urllib2.URLError as e:
                print 'URL Error', e
            except Exception as e:
                print 'General Error', e

            print 'Retrying in one minute'
            time.sleep(60)

        html = unicode(f.read(), 'utf-8')
        f.close()
        self.rewards = []
        self.feed(html)   # feed() starts the HTMLParser parsing
        return self.rewards

    def handle_starttag(self, tag, attributes):
        global status

        attrs = dict(attributes)

        # It turns out that we only care about tags that have a 'class' attribute
        if not 'class' in attrs:
            return

        # The pledge description is in a 'h3' block that has a 'class'
        # attribute of 'pledge__title'.
        if self.in_li_block and 'pledge__title' in attrs['class']:
                self.in_desc_block = True

        # Extract the pledge amount (the cost)
        if self.in_li_block and tag == 'input' and 'pledge__radio' in attrs['class']:
            # remove everything except the actual number
            amount = attrs['title'].encode('ascii', 'ignore')
            nondigits = amount.translate(None, '0123456789.')
            amount = amount.translate(None, nondigits)
            # Convert the value into a float
            self.value = float(amount)
            self.ident = attrs['id']    # Save the reward ID

        # We only care about certain kinds of reward levels -- those that
        # are limited.
        if tag == 'li' and 'pledge--all-gone' in attrs['class']:
            self.in_li_block = True
            self.description = ''

    def handle_endtag(self, tag):
        if tag == 'li':
            if self.in_li_block:
                self.rewards.append((self.value,
                    self.ident,
                    ' '.join(self.description.split())))
            self.in_li_block = False
        if tag == 'h3':
            self.in_desc_block = False

    def handle_data(self, data):
        if self.in_desc_block:
            self.description += self.unescape(data).encode('ascii','ignore')

    def result(self):
        return self.rewards

def pledge_menu(rewards):
    count = len(rewards)

    # If there is only one qualifying pledge level, then just select it
    if count == 1:
        print 'Automatically selecting the only limited award available:'
        print '$%u %s' % (rewards[0][0], rewards[0][2][:74])
        return rewards

    for i in xrange(count):
        print '%u. $%u %s' % (i + 1, rewards[i][0], rewards[i][2][:70])

    while True:
        try:
            ans = raw_input('\nSelect pledge levels: ')
            numbers = map(int, ans.split())
            return [rewards[i - 1] for i in numbers]
        except (IndexError, NameError, SyntaxError):
            continue

def which(program):
    import os

    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None

parser = OptionParser(usage="usage: %prog [options] project-url [command] [cost-of-pledge ...]\n"
                      "Where:\n"
                      " - project-url is the URL of the Kickstarter project.\n"
                      " - command is a command to run once the pledge is available, with the pledge url as a param.\n"
                      " - cost-of-pledge is the cost of the target pledge.\n"
                      "If command is unspecified, it defaults to opening a new browser tab.\n"
                      "If cost-of-pledge is not specified, then a menu of pledges is shown.\n"
                      "Specify cost-of-pledge only if that amount is unique among pledges.\n"
                      "Only restricted pledges are supported.")
parser.add_option("-d", dest="delay",
    help="delay, in minutes, between each check (default is 1)",
    type="int", default=1)
parser.add_option("-v", dest="verbose",
    help="print a message before each delay",
    action="store_true", default=False)

(options, args) = parser.parse_args()

if len(args) < 1:
    parser.error('no URL specified')
    sys.exit(0)

# Command to run
if len(args) > 1 and which(args[1]) is not None:
    command = args[1]
    firstPledgeArg = 2
else:
    command = os.path.dirname(os.path.realpath(sys.argv[0])) + '/openlink.py'
    firstPledgeArg = 1
print 'Command: %s' % command

# Generate the URL
url = args[0].split('?', 1)[0]  # drop the stuff after the ?
url += '/pledge/new' # we want the pledge-editing page
pledges = None   # The pledge amounts on the command line
ids = None       # A list of IDs of the pledge levels
selected = None  # A list of selected pledge levels
rewards = None   # A list of valid reward levels
if len(args) > firstPledgeArg:
    pledges = map(float, args[firstPledgeArg:])

ks = KickstarterHTMLParser()

rewards = ks.process(url)
if not rewards:
    print 'No unavailable limited rewards for this Kickstarter'
    sys.exit(0)

# Select the pledge level(s)
if pledges:
    selected = [r for r in rewards if r[0] in pledges]
else:
    # If a pledge amount was not specified on the command-line, then prompt
    # the user with a menu
    selected = pledge_menu(rewards)

if not selected:
    print 'No reward selected.'
    sys.exit(0)

while True:
    for s in selected:
        if not s[1] in [r[1] for r in rewards]:
            print '%s - Reward available!' % time.strftime('%B %d, %Y %I:%M %p')
            print s[2]
            call([command, url])
            selected = [x for x in selected if x != s]   # Remove the pledge we just found
            if not selected:     # If there are no more pledges to check, then exit
                time.sleep(10)   # Give the web browser time to open
                sys.exit(0)
            break
    if options.verbose:
        print 'Waiting %u minutes ...' % options.delay
    time.sleep(60 * options.delay)

    rewards = ks.process(url)


