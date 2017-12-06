# KEEP Auto Enrol API
import analytics
import StringIO
import json
import logging
import MySQLdb
import re
import time
from datetime import datetime
import requests
from eventtracking import tracker
from util.json_request import JsonResponse, JsonResponseBadRequest
from django.contrib.auth.models import User
from django.shortcuts import redirect
from student.models import (
    CourseEnrollment, unique_id_for_user, anonymous_id_for_user,
    UserProfile, Registration, EntranceExamConfiguration,
    ManualEnrollmentAudit, UNENROLLED_TO_ALLOWEDTOENROLL, ALLOWEDTOENROLL_TO_ENROLLED,
    ENROLLED_TO_ENROLLED, ENROLLED_TO_UNENROLLED, UNENROLLED_TO_ENROLLED,
    UNENROLLED_TO_UNENROLLED, ALLOWEDTOENROLL_TO_UNENROLLED, DEFAULT_TRANSITION_STATE, EnrollmentClosedError, CourseFullError
)
from opaque_keys.edx.locations import SlashSeparatedCourseKey

log = logging.getLogger(__name__)

def show_enrollment_period(request):

  '''
    Function for getting enrolment period
    @input: Get request
    @return: enrollment period or error message : JSON Response
  '''
  if not is_in_keep_ip_range(get_client_ip(request)):
    return JsonResponse(errorMessage("401", "Unauthorize"))

  course_id = request.GET.get('course_id')
  course_id = course_id.replace(" ", "+")

  return JsonResponse(get_enrollment_period(course_id))

def get_enrollment_period(course_id):

  '''
    Query Database and try to objtain the enrollment start/end date
    @input: course_id : String
    @return: result or error object
  '''

  select_clause = " enrollment_start, enrollment_end "
  from_clause = " course_overviews_courseoverview "
  where_clause = " id = \""+ course_id+"\""

  query = "SELECT " + select_clause + " FROM " + from_clause + " WHERE " + where_clause

  conn = MySQLdb.connect("10.11.51.16","edxapp001","password","edxapp")
  cursor = conn.cursor(MySQLdb.cursors.DictCursor)
  cursor.execute(query)
  results = list(cursor) # to array

  cursor.close()
  conn.close()

  if not results:
    # Do not return empty array; Return error message instead
    return errorMessage("404", "Course Not Found: invalid course id")
  else:
    # Return result and convert it to unix timestamp

    if not results[0]['enrollment_start'] is None:
        #convert date time
        original_time = results[0]['enrollment_start']
        results[0]['enrollment_start'] = str(int((original_time - datetime(1970,1,1)).total_seconds()))
    if not results[0]['enrollment_end'] is None:
        #edx date format 2016-09-15 09:00:00.000000
        original_time = results[0]['enrollment_end']
        results[0]['enrollment_end'] = str(int((original_time - datetime(1970,1,1)).total_seconds()))

    return {"total_results": len(results), "results":results }


def auto_enrol(request):

  '''
    Auto enrol by course id and user id
    @input: http request
    @return: redirect to the course page if success
    @return: json response
  '''

  course_id = request.GET.get('course_id')
  # Some brower encode the + to space. i.e. it has to replace back to +
  course_id = course_id.replace(" ", "+")

  # Get the user id from session
  user_id = request.session.get('_auth_user_id')
  user = check_user_exist(user_id)

  results = {
    'error': True,
    'description': 'User does not exist. Please contact support@keep.edu.hk',
  }

  if user != None:
    try: 
      enrol_obj = enrol_user(user, course_id)
    except CourseFullError:
      results = {
        'error': True,
        'description': 'Course enrolment full. Please contact support@keep.edu.hk',
      }
      return JsonResponse(results)
    except EnrollmentClosedError:
      results = {
        'error': True,
        'description': 'Not allowed to enrol in course, might be enrolment closed or invitation only or not yet started. Please contact support@keep.edu.hk',
      }
      raise KeyError
      #return JsonResponse(results)
    # TODO: Change the URL in production deployment
    redirect_url = 'https://ficusedx.keep.edu.hk/courses/'+course_id +'/info'
    return redirect(redirect_url);

  return JsonResponse(results)


def check_user_exist(id):

  '''
    Check user exist with id
    @input: id
    @return: user object if exist, else None
  '''

  if id == None:
    return None
  if User.objects.filter(id=id).exists():
    user = User.objects.get(id=id)
    return user
  else:
    return None


def enrol_user(user, course_id):

  '''
   Enrol user and log with to edx trakcing log
   @input: user: user object
   @input: course_id: string
   @return: enrolment object
  '''

  course_id = SlashSeparatedCourseKey.from_deprecated_string(course_id)
  # enrol and emit event to tracker
  try: 
    enrollment_obj = CourseEnrollment.enroll(user, course_id,check_access=True)
    profile = UserProfile(user=user)
  except EnrollmentClosedError:
    raise EnrollmentClosedError
  except CourseFullError:
    raise CourseFullError
  except:
    enrollment_obj = None
    pass
    
  reason = 'Enrolling via auto enrol api'
  manual_enroll_audit = ManualEnrollmentAudit.create_manual_enrollment_audit(
    user,
    user.email,
    ENROLLED_TO_ENROLLED,
    reason,
    enrollment_obj
  )

  #lms/edx.log
  log.info(
    u'user %s enrolled in the course %s',
    user.username,
    course_id,
  )

  return enrollment_obj


def errorMessage(code, message):

  '''
   Build error message
   @input: code: int
   @input: message: string
   @return: object for building JSON
  '''

  return {"error" : {"code" : code, "message" : message}}

def get_client_ip(request):
  x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
  if x_forwarded_for:
    ip = x_forwarded_for.split(',')[0]
  else:
    ip = request.META.get('REMOTE_ADDR')
  return ip

def is_in_keep_ip_range(ip):
  #TODO: Change in actual production server to prevent unauthorized access
  return (ip[:8] in ('10.11.0.', '10.11.1.', '10.11.2.', '10.11.3.', '10.11.4.', '10.11.5.'))
  #return True
