#!/usr/bin/python
#
# Originally taken from http://bluedrag.dreamwidth.org/296158.html and further modified
#
# Usage:
# 1) Get the ljdump.py script, create ljdump.config, run ljdump
# 2) set env var DIFF to your favorite diffing program (I used patdiff)
# 3) Run this script in the directory where ldjump.config is. Examine the diff and answer questions
# 

import codecs, os, pickle, pprint, re, shutil, sys, urllib2, xml.dom.minidom, xmlrpclib
import subprocess
import glob
import re
import xml.etree.ElementTree as ET

url = {}
posts = {}

try:
    from hashlib import md5
except ImportError:
    import md5 as _md5
    md5 = _md5.new

def calcchallenge(challenge, password):
    return md5(challenge+md5(password).hexdigest()).hexdigest()

def flatresponse(response):
    r = {}
    while True:
        name = response.readline()
        if len(name) == 0:
            break
        if name[-1] == '\n':
            name = name[:len(name)-1]
        value = response.readline()
        if value[-1] == '\n':
            value = value[:len(value)-1]
        r[name] = value
    return r

def getljsession(server, username, password):
    r = urllib2.urlopen(server+"/interface/flat", "mode=getchallenge")
    response = flatresponse(r)
    r.close()
    r = urllib2.urlopen(server+"/interface/flat", "mode=sessiongenerate&user=%s&auth_method=challenge&auth_challenge=%s&auth_response=%s" % (username, response['challenge'], calcchallenge(response['challenge'], password)))
    response = flatresponse(r)
    r.close()
    return response['ljsession']

def dochallenge(server, params, password):
    challenge = server.LJ.XMLRPC.getchallenge()
    params.update({
        'auth_method': "challenge",
        'auth_challenge': challenge['challenge'],
        'auth_response': calcchallenge(challenge['challenge'], password)
    })
    return params


def process(server_url, username, password, journal):
    for filename in sorted(glob.glob(journal+'/L-*')):
         try:
             tree = ET.parse(filename)
         except ET.ParseError as e:
             print '%s: %s' % (filename, e)
             continue
         root = tree.getroot()
         dw_url = root.find('url').text
         try:
             import_source = root.find('props').find('import_source').text
         except AttributeError:
             print '%s: LJ url not found' % filename
             continue

         # usernames with underscores are handled differently
         if re.search(r'livejournal\.com/_',import_source):
             lj_url = re.sub(r'livejournal\.com/(.*?)/(.*)', r'http://users.livejournal.com/\1/\2.html', import_source)
             # If nick had undescores, URLs might contain both _nick_ and -nick-
             # Lets handle both cases
             url[lj_url] = dw_url
             url[re.sub('_','-',lj_url)] = dw_url
         else:
             lj_url = re.sub(r'livejournal\.com/(.*?)/(.*)', r'http://\1.livejournal.com/\2.html', import_source)
             url[lj_url] = dw_url
         posts[dw_url] = root
         

    ljsession = getljsession(server_url, username, password)
    server = xmlrpclib.ServerProxy(server_url + "/interface/xmlrpc")
         
    for dw_url, post in sorted(posts.iteritems()):
        old_text = post.find('event').text
        new_text = re.sub(r'http://([\w\d_-]+)\.livejournal\.com/tag/',
                          r'http://\1.dreamwidth.org/tag/', old_text)
        for lj, dw in url.iteritems():
            new_text = new_text.replace(lj, dw)

        if old_text != new_text:
            new_f = open("/tmp/new","w")
            new_f.write(new_text.encode('utf-8'))
            new_f.close()

            old_f = open("/tmp/old","w")
            old_f.write(old_text.encode('utf-8'))
            old_f.close()

            diff = os.getenv('DIFF','/usr/bin/diff')
            subprocess.call([diff,"/tmp/old","/tmp/new"])
            # print new_text
            # print dw_url

            itemid = post.find('itemid').text
            try:
                subject = post.find('subject').text
            except AttributeError:
                subject = ''

            print
            print itemid, dw_url, subject
            s = raw_input('Proceed? (y/n) ')
            if s != 'y':
                continue
            
            e = server.LJ.XMLRPC.editevent(dochallenge(server, {
                'username': username,
                'ver': 1,
                'event': new_text,
                'itemid': itemid,
                'subject': subject,
                #'lineendings': 'unix',
            }, password))
            print "Edit result:", e
            print
            
if os.access("ljdump.config", os.F_OK):
    config = xml.dom.minidom.parse("ljdump.config")
    server = config.documentElement.getElementsByTagName("server")[0].childNodes[0].data
    username = config.documentElement.getElementsByTagName("username")[0].childNodes[0].data
    password = config.documentElement.getElementsByTagName("password")[0].childNodes[0].data
    journals = config.documentElement.getElementsByTagName("journal")
    if journals:
        for e in journals:
            print server, username, password, e.childNodes[0].data
            process(server, username, password, e.childNodes[0].data)
    else:
        process(server, username, password, username)
