#!/usr/bin/python
import sys
import json
import MySQLdb
import subprocess
import copy
import re
from os.path import isfile
from collections import OrderedDict
from pymongo import MongoClient
from bson.objectid import ObjectId

users      = {}
user_roles = {}
courses    = {}

# Prepare for discussion-related query
mongoclient = MongoClient(host=["10.11.5.17", "10.11.5.20", "10.11.5.21"], replicaSet="mongoclusterprod")
edxdb       = mongoclient.edxapp
forumdb     = mongoclient.cs_comments_service

base_domain = 'edx.keep.edu.hk'
base_url    = 'https://' + base_domain

def expandLog(line):
    log = json.loads(line)

    # Do not process if
    # 1) no user is logged in; or
    # 2) event does not come from client's view (e.g. edxstudio)
    if (log['username'] == '') or (log['host'] != base_domain):
        return False

    event = log['event_type']

    # Set up default xAPI verb and object (generic event)
    xapi = {
        'keep_id'        : 'Unknown user KEEP id', # placeholder
        'user_id'        : log['context']['user_id'],
        'user_name'      : log['username'],
        'user_email'     : 'Unknown user email',   # placeholder
        'user_role'      : 'student',              # placeholder (treated as student if there is no proper enrollment)
        'verb_id'        : 'http://adlnet.gov/expapi/verbs/interacted',
        'verb_display'   : 'interacted with',
        'object_id'      : 'https://' + log['host'],
        'object_display' : 'Open edX',
        'object_desc'    : None,
        'course_id'      : log['context']['course_id'],
        'course_name'    : '',
        'ip_addr'        : log['ip'],
        'timestamp'      : log['time'],
        'result'         : None,
    }

    # Get user's email address and KEEP id if they are available
    if log['username'] in users:
        xapi['user_email'] = users[log['username']]['email']
        xapi['keep_id'] = users[log['username']]['keepid']

    # Get course display name by course id
    if log['context']['course_id'] in courses:
        xapi['course_name'] = courses[log['context']['course_id']]

    # Get user's role in the course
    course_user = log['context']['course_id'] + ':' + log['username']
    if course_user in user_roles:
        xapi['user_role'] = user_roles[course_user]

    # Container of the extended log objects.
    # We expect multiple events can be extracted from one log line.
    # (currently only applicable to log-in event)
    xapis = []

    # User has just logged in if he/she is redirect from account.keep.edu.hk
    if log['referer'][:28] == 'https://account.keep.edu.hk/':
        # event should store the page the user arrived.
        # In case it is the root, then the next event should contain the correct page
        # and we can ignore this one.
        if event == '/':
            return False

        xapi['verb_id'] = 'https://brindlewaye.com/xAPITerms/verbs/loggedin/'
        xapi['verb_display'] = 'logged in to'

        # Login info is mixed inside an event.
        # The xapi object is "duplicated" and appended to the container.
        # Then we continue to parse the same log line.
        xapis.append(copy.deepcopy(xapi))

    if event == '/i18n.js':
        # Useless events that we want to skip
        return False

    elif event == '/dashboard':
        # User viewed dashboard (list of current courses)
        xapi['verb_id'] = 'http://id.tincanapi.com/verb/viewed'
        xapi['verb_display'] = 'viewed'
        xapi['object_id'] += '/dashboard'
        xapi['object_display'] = 'Dashboard'

    elif event == '/courses':
        # User viewed the find courses page
        xapi['verb_id'] = 'http://id.tincanapi.com/verb/viewed'
        xapi['verb_display'] = 'viewed'
        xapi['object_id'] += '/courses'
        xapi['object_display'] = 'Find Courses page'

    elif event == '/logout':
        # User logged out the system
        xapi['verb_id'] = 'https://brindlewaye.com/xAPITerms/verbs/loggedout/'
        xapi['verb_display'] = 'logged out of'

    elif (event == 'seq_goto') or (event == 'seq_next') or (event == 'seq_prev'):
        # A page was finished loading (down to unit level)
        xapi['verb_id'] = 'http://id.tincanapi.com/verb/viewed'
        xapi['verb_display'] = 'viewed'
        xapi['object_id'] = log['page'] + str(json.loads(log['event'])['new'])
        xapi['object_display'] = 'a courseware page'

    elif event == 'edx.asset.viewed':
        # User viewd an asset
        xapi['verb_id'] = 'http://id.tincanapi.com/verb/viewed'
        xapi['verb_display'] = 'viewed'
        xapi['object_id'] += log['context']['path']
        xapi['object_display'] = 'a courseware asset'
        # Extrac only the file name
        xapi['object_desc'] = log['context']['path'].split('@').pop()

    elif event == 'problem_check':
        # A question was answered
        if 'submission' in log['event']:
            xapi['verb_id'] = 'http://adlnet.gov/expapi/verbs/attempted'
            xapi['verb_display'] = 'attempted'
            xapi['object_id'] = getUnitByBlock('problem', log['event']['problem_id'].split('@').pop(), log['context']['course_id'], log['referer'])
            xapi['object_display'] = 'a problem'

            # Create the result object
            xapi['result'] = OrderedDict([
                ('score' , OrderedDict([
                    ('raw' , log['event']['grade']),
                    ('max' , log['event']['max_grade'])
                ])),
                ('response' , log['event']['success'])
            ])

    elif event == 'problem_graded':
        # A question was checked
        xapi['verb_id'] = 'http://activitystrea.ms/schema/1.0/complete'
        xapi['verb_display'] = 'completed'
        xapi['object_id'] = getUnitByBlock('problem', log['event'][0].split('_')[1], log['context']['course_id'], log['referer'])
        xapi['object_display'] = 'a problem'

    elif event == 'load_video':
        # A video was loaded into the unit page
        xapi['verb_id'] = 'http://course.keep.edu.hk/xapi/verbs/load'
        xapi['verb_display'] = 'loaded'
        xapi['object_id'] = getUnitByBlock('video', json.loads(log['event'])['id'], log['context']['course_id'], log['page'])
        xapi['object_display'] = 'a video'

    elif event == 'play_video':
        # User started playing a video
        xapi['verb_id'] = 'http://activitystrea.ms/schema/1.0/start'
        xapi['verb_display'] = 'started playing'
        xapi['object_id'] = getUnitByBlock('video', json.loads(log['event'])['id'], log['context']['course_id'], log['page'])
        xapi['object_display'] = 'a video'

    elif event == 'pause_video':
        # User paused playing a video
        xapi['verb_id'] = 'http://id.tincanapi.com/verb/paused'
        xapi['verb_display'] = 'paused playing'
        xapi['object_id'] = getUnitByBlock('video', json.loads(log['event'])['id'], log['context']['course_id'], log['page'])
        xapi['object_display'] = 'a video'

    elif event == 'stop_video':
        # User stopped playing a video
        xapi['verb_id'] = 'http://course.keep.edu.hk/xapi/verbs/stop'
        xapi['verb_display'] = 'stopped playing'
        xapi['object_id'] = getUnitByBlock('video', json.loads(log['event'])['id'], log['context']['course_id'], log['page'])
        xapi['object_display'] = 'a video'

    elif event == 'seek_video':
        # User used the seekbar of the video player
        xapi['verb_id'] = 'http://course.keep.edu.hk/xapi/verbs/seek'
        xapi['verb_display'] = 'seeked'
        xapi['object_id'] = getUnitByBlock('video', json.loads(log['event'])['id'], log['context']['course_id'], log['page'])
        xapi['object_display'] = 'a video'

    elif event == 'show_transcript':
        # User showed the transcript in the video player
        xapi['verb_id'] = 'http://course.keep.edu.hk/xapi/verbs/show'
        xapi['verb_display'] = 'showed'
        xapi['object_id'] = getUnitByBlock('video', json.loads(log['event'])['id'], log['context']['course_id'], log['page'])
        xapi['object_display'] = 'a video transcript'

    elif event == 'hide_transcript':
        # User hid the transcript in the video player
        xapi['verb_id'] = 'http://course.keep.edu.hk/xapi/verbs/hide'
        xapi['verb_display'] = 'hid'
        xapi['object_id'] = getUnitByBlock('video', json.loads(log['event'])['id'], log['context']['course_id'], log['page'])
        xapi['object_display'] = 'a video transcript'

    elif event == 'edx.forum.thread.created':
        # User created a new discussion post
        xapi['verb_id'] = 'http://activitystrea.ms/schema/1.0/create'
        xapi['verb_display'] = 'created'
        xapi['object_id'] += '/courses/' + xapi['course_id'] + '/discussion/forum/' + log['event']['commentable_id'] + '/threads/' + log['event']['id']
        xapi['object_display'] = 'a discussion thread'
        xapi['object_desc'] = log['event']['title']

    elif event == 'edx.forum.response.created':
        # User replied a discussion post
        xapi['verb_id'] = 'http://adlnet.gov/expapi/verbs/responded'
        xapi['verb_display'] = 'responded to'
        xapi['object_id'] += '/courses/' + xapi['course_id'] + '/discussion/forum/' + log['event']['commentable_id'] + '/threads/' + log['event']['discussion']['id'] + \
                             '#response_' + log['event']['id']
        xapi['object_display'] = 'a discussion thread'
        xapi['object_desc'] = getDiscussion('title', log['event']['discussion']['id'])

    elif event == 'edx.forum.comment.created':
        # User replied a discussion reply
        xapi['verb_id'] = 'http://adlnet.gov/expapi/verbs/responded'
        xapi['verb_display'] = 'responded to'
        xapi['object_id'] += '/courses/' + xapi['course_id'] + '/discussion/forum/' + log['event']['commentable_id'] + '/threads/' + log['event']['discussion']['id'] + \
                             '#response_' + log['event']['response']['id'] + '+comment_' + log['event']['id']
        xapi['object_display'] = 'a discussion response'
        xapi['object_desc'] = getDiscussion('title', log['event']['discussion']['id'])

    elif event == 'edx.course.student_notes.notes_page_viewed':
        # User viewed the Notes page
        xapi['verb_id'] = 'http://id.tincanapi.com/verb/viewed'
        xapi['verb_display'] = 'viewed'
        xapi['object_id'] = log['page']
        xapi['object_display'] = 'course note page'

    elif event == 'edx.course.student_notes.viewed':
        # User hovered on a note
        xapi['verb_id'] = 'http://id.tincanapi.com/verb/viewed'
        xapi['verb_display'] = 'viewed'
        xapi['object_id'] = log['page'] + json.loads(log['event'])['notes'][0]['note_id']
        xapi['object_display'] = 'a note'

    elif event == 'edx.course.student_notes.added':
        # User created a note
        xapi['verb_id'] = 'http://activitystrea.ms/schema/1.0/create'
        xapi['verb_display'] = 'created'
        xapi['object_id'] = log['page'] + json.loads(log['event'])['note_id']
        xapi['object_display'] = 'a note'

    elif event == 'edx.course.student_notes.edited':
        # User edited a note
        xapi['verb_id'] = 'http://curatr3.com/define/verb/edited'
        xapi['verb_display'] = 'edited'
        xapi['object_id'] = log['page'] + json.loads(log['event'])['note_id']
        xapi['object_display'] = 'a note'

    elif event == 'edx.course.student_notes.searched':
        # User searched for a note
        xapi['verb_id'] = 'http://activitystrea.ms/schema/1.0/search'
        xapi['verb_display'] = 'searched for'
        xapi['object_id'] = log['page']
        xapi['object_display'] = 'a note'

    elif event == 'edx.course.student_notes.deleted':
        # User deleted a note
        xapi['verb_id'] = 'http://activitystrea.ms/schema/1.0/delete'
        xapi['verb_display'] = 'deleted'
        xapi['object_id'] = log['page'] + json.loads(log['event'])['note_id']
        xapi['object_display'] = 'a note'

    elif event == 'openassessmentblock.create_submission':
        # User submitted a peer assessment
        xapi['verb_id'] = 'http://activitystrea.ms/schema/1.0/submit'
        xapi['verb_display'] = 'submitted'
        xapi['object_id'] = getUnitByBlock('openassessment', log['context']['module']['usage_key'].split('@').pop(), log['context']['course_id'], log['referer'])
        xapi['object_display'] = 'a peer assessment'

    elif event == 'openassessment.student_training_assess_example':
        # User submitted a peer assessment training
        xapi['verb_id'] = 'http://adlnet.gov/expapi/verbs/attempted'
        xapi['verb_display'] = 'attempted'
        xapi['object_id'] = getUnitByBlock('openassessment', log['context']['module']['usage_key'].split('@').pop(), log['context']['course_id'], log['referer'])
        xapi['object_display'] = 'a peer assessment training'

    elif event in ['openassessmentblock.peer_assess', 'openassessmentblock.self_assess']:
        # User assessed either a peer submission or his/her own peer assessment response
        xapi['verb_id'] = 'http://www.tincanapi.co.uk/verbs/evaluated'
        xapi['verb_display'] = 'evaluated'
        xapi['object_id'] = getUnitByBlock('openassessment', log['context']['module']['usage_key'].split('@').pop(), log['context']['course_id'], log['referer'])
        if event == 'openassessmentblock.self_assess':
            xapi['object_display'] = 'own peer assessment response'
        else:
            xapi['object_display'] = 'a peer assessment submission'

        # Create the result object
        points = 0
        maxpoints = 0
        for part in log['event']['parts']:
            points += int(part['option']['points'])
            maxpoints += int(part['criterion']['points_possible'])
        xapi['result'] = {
            'score' : {
                'raw' : points,
                'max' : maxpoints
            },
            'response' : log['event']['feedback']
        }

    elif event == 'edx.course.enrollment.activated':
        # User registered himself/herself into a course
        xapi['verb_id'] = 'http://www.tincanapi.co.uk/verbs/enrolled_onto_learning_plan'
        xapi['verb_display'] = 'enrolled onto'
        xapi['object_id'] += '/courses/' + log['context']['course_id']
        xapi['object_display'] = log['context']['course_id']

    elif event == 'edx.course.enrollment.deactivated':
        # User unenrolled himself/herself from a course
        xapi['verb_id'] = 'http://activitystrea.ms/schema/1.0/leave'
        xapi['verb_display'] = 'left'
        xapi['object_id'] += '/courses/' + log['context']['course_id']
        xapi['object_display'] = log['context']['course_id']

    else:
        # event_type is not straight forward and we need to do regular expression checking
        # Useless events that we want to skip
        if re.match('^\/courses\/.+\/edxnotes\/token\/$', event):
            return False

        if re.match('^\/courses\/.+\/courseware\/.*$', event):
            # A page was finished loading (only down to subsection level)
            xapi['verb_id'] = 'http://id.tincanapi.com/verb/viewed'
            xapi['verb_display'] = 'viewed'
            xapi['object_id'] += log['context']['path']
            xapi['object_display'] = 'a courseware page'

        ## The following events are about discussion forums ##

        elif re.match('^\/courses\/.+\/discussion\/forum$', event):
            xapi['verb_id'] = 'http://id.tincanapi.com/verb/viewed'
            xapi['verb_display'] = 'viewed'
            xapi['object_id'] += log['context']['path']
            xapi['object_display'] = 'course discussion page'

        elif re.match('^\/courses\/.+\/discussion\/forum\/.+\/threads\/.+$', event):
            xapi['verb_id'] = 'http://id.tincanapi.com/verb/viewed'
            xapi['verb_display'] = 'viewed'
            xapi['object_id'] += event
            xapi['object_display'] = 'a discussion thread'
            xapi['object_desc'] = getDiscussion('title', event.split('/').pop())

        elif re.match('^\/courses\/.+\/discussion\/threads\/.+\/update$', event):
            xapi['verb_id'] = 'http://activitystrea.ms/schema/1.0/update'
            xapi['verb_display'] = 'updated'
            thread_id = log['context']['path'].replace('/update', '').split('/').pop()
            subevent = json.loads(log['event'])
            xapi['object_id'] += '/courses/' + xapi['course_id'] + '/discussion/forum/' + subevent['POST']['commentable_id'][0] + '/threads/' + thread_id
            xapi['object_display'] = 'a discussion thread'
            xapi['object_desc'] = subevent['POST']['title'][0]

        elif re.match('^\/courses\/.+\/discussion\/comments\/.+\/update$', event):
            xapi['verb_id'] = 'http://activitystrea.ms/schema/1.0/update'
            xapi['verb_display'] = 'updated'
            d = getDiscussionByComment(log['context']['path'])
            xapi['object_id']  += d[0]
            xapi['object_desc'] = d[1]
            xapi['object_display'] = 'a discussion response'

        elif re.match('^\/courses\/.+\/discussion\/threads\/.+\/delete$', event):
            xapi['verb_id'] = 'http://activitystrea.ms/schema/1.0/delete'
            xapi['verb_display'] = 'deleted'
            xapi['object_id'] += log['context']['path'].replace('/delete', '')
            xapi['object_display'] = 'a discussion thread'

        elif re.match('^\/courses\/.+\/discussion\/comments\/.+\/delete$', event):
            xapi['verb_id'] = 'http://activitystrea.ms/schema/1.0/delete'
            xapi['verb_display'] = 'deleted'
            xapi['object_id'] += log['context']['path'].replace('/delete', '')
            xapi['object_display'] = 'a discussion response'

        elif re.match('^\/courses\/.+\/discussion\/threads\/.+\/follow$', event):
            xapi['verb_id'] = 'http://activitystrea.ms/schema/1.0/follow'
            xapi['verb_display'] = 'followed'
            d = getDiscussionByThread(log['context']['path'])
            xapi['object_id']  += d[0]
            xapi['object_desc'] = d[1]
            xapi['object_display'] = 'a discussion thread'

        elif re.match('^\/courses\/.+\/discussion\/threads\/.+\/unfollow$', event):
            xapi['verb_id'] = 'http://activitystrea.ms/schema/1.0/stop-following'
            xapi['verb_display'] = 'stopped following'
            d = getDiscussionByThread(log['context']['path'])
            xapi['object_id']  += d[0]
            xapi['object_desc'] = d[1]
            xapi['object_display'] = 'a discussion thread'

        elif re.match('^\/courses\/.+\/discussion\/threads\/.+\/upvote$', event):
            xapi['verb_id'] = 'http://id.tincanapi.com/verb/voted-up'
            xapi['verb_display'] = 'up voted'
            d = getDiscussionByThread(log['context']['path'])
            xapi['object_id']  += d[0]
            xapi['object_desc'] = d[1]
            xapi['object_display'] = 'a discussion thread'

        elif re.match('^\/courses\/.+\/discussion\/threads\/.+\/unvote$', event):
            xapi['verb_id'] = 'http://id.tincanapi.com/verb/voted-down'
            xapi['verb_display'] = 'down voted'
            d = getDiscussionByThread(log['context']['path'])
            xapi['object_id']  += d[0]
            xapi['object_desc'] = d[1]
            xapi['object_display'] = 'a discussion thread'

        elif re.match('^\/courses\/.+\/discussion\/comments\/.+\/upvote$', event):
            xapi['verb_id'] = 'http://id.tincanapi.com/verb/voted-up'
            xapi['verb_display'] = 'up voted'
            d = getDiscussionByComment(log['context']['path'])
            xapi['object_id']  += d[0]
            xapi['object_desc'] = d[1]
            xapi['object_display'] = 'a discussion response'

        elif re.match('^\/courses\/.+\/discussion\/comments\/.+\/unvote$', event):
            xapi['verb_id'] = 'http://id.tincanapi.com/verb/voted-down'
            xapi['verb_display'] = 'down voted'
            d = getDiscussionByComment(log['context']['path'])
            xapi['object_id']  += d[0]
            xapi['object_desc'] = d[1]
            xapi['object_display'] = 'a discussion response'

        elif re.match('^\/courses\/.+\/discussion\/threads\/.+\/flagAbuse$', event):
            xapi['verb_id'] = 'http://activitystrea.ms/schema/1.0/flag-as-inappropriate'
            xapi['verb_display'] = 'flagged'
            d = getDiscussionByThread(log['context']['path'])
            xapi['object_id']  += d[0]
            xapi['object_desc'] = d[1]
            xapi['object_display'] = 'a discussion thread'

        elif re.match('^\/courses\/.+\/discussion\/threads\/.+\/unFlagAbuse$', event):
            xapi['verb_id'] = 'http://course.keep.edu.hk/xapi/verbs/unflag-as-inappropriate'
            xapi['verb_display'] = 'unflagged'
            d = getDiscussionByThread(log['context']['path'])
            xapi['object_id']  += d[0]
            xapi['object_desc'] = d[1]
            xapi['object_display'] = 'a discussion thread'

        elif re.match('^\/courses\/.+\/discussion\/comments\/.+\/flagAbuse$', event):
            xapi['verb_id'] = 'http://activitystrea.ms/schema/1.0/flag-as-inappropriate'
            xapi['verb_display'] = 'flagged'
            d = getDiscussionByComment(log['context']['path'])
            xapi['object_id']  += d[0]
            xapi['object_desc'] = d[1]
            xapi['object_display'] = 'a discussion response'

        elif re.match('^\/courses\/.+\/discussion\/comments\/.+\/unFlagAbuse$', event):
            xapi['verb_id'] = 'http://course.keep.edu.hk/xapi/verbs/unflag-as-inappropriate'
            xapi['verb_display'] = 'unflagged'
            d = getDiscussionByComment(log['context']['path'])
            xapi['object_id']  += d[0]
            xapi['object_desc'] = d[1]
            xapi['object_display'] = 'a discussion response'

        ## The following events are about the top Pages ##

        elif re.match('^\/courses\/.+\/info$', event):
            xapi['verb_id'] = 'http://id.tincanapi.com/verb/viewed'
            xapi['verb_display'] = 'viewed'
            xapi['object_id'] += log['context']['path']
            xapi['object_display'] = 'course info page'

        elif re.match('^\/courses\/.+\/about$', event):
            xapi['verb_id'] = 'http://id.tincanapi.com/verb/viewed'
            xapi['verb_display'] = 'viewed'
            xapi['object_id'] += log['context']['path']
            xapi['object_display'] = 'course about page'

        elif re.match('^\/courses\/.+\/progress$', event):
            xapi['verb_id'] = 'http://id.tincanapi.com/verb/viewed'
            xapi['verb_display'] = 'viewed'
            xapi['object_id'] += log['context']['path']
            xapi['object_display'] = 'course progress page'

        elif re.match('^\/courses\/.+\/course_wiki$', event):
            xapi['verb_id'] = 'http://id.tincanapi.com/verb/viewed'
            xapi['verb_display'] = 'viewed'
            xapi['object_id'] += log['context']['path']
            xapi['object_display'] = 'course wiki page'

    # Append the extended log object to the list and then return the list
    xapis.append(xapi)
    return xapis


def translateLog(xapi, line):
    # Create xAPI statement
    stmt = OrderedDict([
        ('actor' , OrderedDict([
            ('objectType' , 'Agent'),
            ('name' , xapi['keep_id']),
            ('account' , OrderedDict([
                ('name' , xapi['user_name']),
                ('homePage' , base_url)
            ]))
        ])),
        ('verb' , OrderedDict([
            ('display' , {
                'en-US' : xapi['verb_display']
            }),
            ('id' , xapi['verb_id'])
        ])),
        ('object' , OrderedDict([
            ('id' , xapi['object_id']),
            ('definition' , OrderedDict([
                ('name' , {
                    'en-US' : xapi['object_display']
                }),
                ('description' , {
                    'en-US' : xapi['object_desc']
                })
            ]))
        ])),
        ('result' , xapi['result']),
        ('context' , OrderedDict([
            ('platform' , 'Open edX'),
            ('extensions' , OrderedDict([
                ('http://lrs.learninglocker.net/define/extensions/open_edx_tracking_log' , OrderedDict([
                    ('userid' , xapi['user_id']),
                    ('mbox' , 'mailto:' + xapi['user_email']),
                    ('courseid' , xapi['course_id']),
                    ('coursename' , xapi['course_name']),
                    ('role' , xapi['user_role']),
                    ('other' , line),
                    ('ip' , xapi['ip_addr'])
                ]))
            ]))
        ])),
        ('timestamp' , xapi['timestamp'])
    ])

    # Only 'problem_check' and 'openassessmentblock.peer_assess' events contain results.
    # For other event, remove the result node.
    if xapi['result'] is None:
        del stmt['result']

    # Onlt asset and forum events use object description.
    # For other event, remove the description node.
    if xapi['object_desc'] is None:
        del stmt['object']['definition']['description']

    return stmt


def parseLog(line):
    
    # Do not process an empty line
    if line == '':
        return
    
    xapis = expandLog(line)
    if xapis == False:
        return

    # A log line can be expanded into multiple events. Iterate each of them.
    for xapi in xapis:
        recipe = translateLog(xapi, line)
        if recipe == False:
            return

        # Print statement as one line to stdout
        print(json.dumps(recipe))


def getDiscussion(field, discussion_id):
    if (field == '') or (discussion_id == ''):
        return ''

    # Given the discussion ID, get the required attribute from MongoDB
    thread = forumdb.contents.find_one({'_id':ObjectId(discussion_id)},{'_id':False,field:True})
    if thread is not None:
        if field in thread:
            return str(thread[field])  # cast to string for possible ObjectID type

    return ''


def getDiscussionByThread(contextpath):
    last_slash = contextpath.rfind('/')
    path = contextpath[:last_slash]
    path_array = path.split('/')
    thread_id = path_array.pop()
    forum_id = getDiscussion('commentable_id', thread_id)

    if forum_id != '':
        course_id = path_array[2]
        return [
            '/courses/' + course_id + '/discussion/forum/' + forum_id + '/threads/' + thread_id,
            getDiscussion('title', thread_id)
        ]

    else:
        # Thread has been deleted and therefore cannot reassemble URL to the object.
        # Fallback to use context path, which does not bring back to the original thread.
        return [ path, '' ]


def getDiscussionByComment(contextpath):
    last_slash = contextpath.rfind('/')
    path = contextpath[:last_slash]
    path_array = path.split('/')
    comment_id = path_array.pop()
    thread_id = getDiscussion('comment_thread_id', comment_id)

    if thread_id != '':
        course_id = path_array[2]
        forum_id = getDiscussion('commentable_id', thread_id)

        # Determine whether this is a response or a comment
        response_id = getDiscussion('parent_id', comment_id)
        anchor = ''
        if response_id == '':
            anchor = '#response_' + comment_id
        else:
            anchor = '#response_' + response_id + '+comment_' + comment_id

        return [ 
            '/courses/' + course_id + '/discussion/forum/' + forum_id + '/threads/' + thread_id + anchor,
            getDiscussion('title', thread_id)
        ]

    else:
        # Either thread or response has been deleted and therefore cannot reassemble URL to the object.
        # Fallback to use context path, which does not bring back to the original thread.
        return [ path, '' ]


def getUnitByBlock(block_type, block_id, course_id, fallback_url):
    # Find out the unit containing the block.
    # Although modulestore.structures stores the block editing history, since block cannot be moved between units,
    # we can safely assume that any of the returned unit-block relationships are valid.
    unit = edxdb.modulestore.structures.find_one({'blocks.fields.children':[block_type,block_id]},{'_id':False,'blocks.$':True})
    # Form a direct link to the unit
    if unit is not None:
        return base_url + '/courses/' + course_id + '/jump_to_id/' + unit['blocks'][0]['block_id'] + '#' + block_type + '_' + block_id
    else:
        return fallback_url + '#' + block_type + '_' + block_id


""" main() """

# Require one command-line argument
if len(sys.argv) < 2:
    print >> sys.stderr, 'ERROR: missing argument'
    sys.exit()

# Require the argument to be a valid file name
delta = sys.argv[1]
if not isfile(delta):
    print >> sys.stderr, 'ERROR: invalid delta file'
    sys.exit()

# Get distinct usernames and course IDs from the log delta
delta_users = subprocess.check_output("jq --compact-output '.username' " + delta + " | sort | uniq | sed '/^\"\"$/d' | paste -d, -s", shell=True).strip()
delta_courses = subprocess.check_output("jq --compact-output '.context.course_id' " + delta + " | sort | uniq | sed '/^\"\"$/d' | paste -d, -s", shell=True).strip()

# Quit if there is no user to process
if delta_users == '':
    sys.exit()

conn = MySQLdb.connect(
  settings.DATABASES['default']['HOST'],
  settings.DATABASES['default']['USER'],
  settings.DATABASES['default']['PASSWORD'],
  settings.DATABASES['default']['NAME'],
)
cursor = conn.cursor(MySQLdb.cursors.DictCursor)

# Prepare three mapping tables
# 1) user email and keep ID
query = 'SELECT u.username,u.email,x.external_id FROM external_auth_externalauthmap AS x JOIN auth_user AS u ON x.user_id = u.id WHERE u.username IN (' + delta_users + ');'
cursor.execute(query)
for item in cursor:
    users[item['username']] = { 'email' : item['email'] , 'keepid' : item['external_id'] }

if delta_courses != '':
    # 2) course name
    query = 'SELECT id,display_name FROM course_overviews_courseoverview WHERE id IN (' + delta_courses + ') ;'
    cursor.execute(query)
    for item in cursor:
        courses[item['id']] = item['display_name']

    # 3) user role in course
    query = 'SELECT CONCAT(c.id,":",u.username) AS course_user, (CASE WHEN u.is_superuser = 1 THEN "superuser" WHEN ar.role IS NOT NULL THEN ar.role ELSE "student" END) AS role FROM student_courseenrollment AS e JOIN auth_user AS u ON e.user_id = u.id JOIN course_overviews_courseoverview AS c ON e.course_id = c.id LEFT JOIN student_courseaccessrole AS ar ON e.course_id = ar.course_id AND e.user_id = ar.user_id WHERE u.username IN (' + delta_users + ') AND c.id IN (' + delta_courses + ');'
    cursor.execute(query)
    for item in cursor:
        user_roles[item['course_user']] = item['role']

cursor.close()
conn.close()

# Transform each log in the delta file into xAPI statement
with open(delta, 'r') as f:
    for line in f:
        try: # skip problematic log without terminating the whole script
            parseLog(line.strip())
        except: # catch *all* exceptions
            print >> sys.stderr, 'Error parsing log: ' + line

# Remember to disconnect from MongoDB
mongoclient.close()


