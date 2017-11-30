# KEEP Open edX Course API

import json
import pymongo
import MySQLdb
import re
import base64
import requests
from pymongo import MongoClient
from bson.objectid import ObjectId
from django.http import (HttpRequest)
from django.http import (HttpResponse)
from django.http import (HttpResponseRedirect)


def show_public_courses(request):
  # List public courses (no authentication required)
  return outputJSON(get_keepcourses())


def show(request, action=""):
  authenticated = 0
  valid_api_users = [
    "FICUS_KEEP_TESTBOT"
    ]

  # Adopt part of the codes from basic authentication snippet
  # (https://www.djangosnippets.org/snippets/243/)
  # (https://github.com/m7v8/django-basic-authentication-decorator)
  if 'HTTP_AUTHORIZATION' in request.META:
    auth = request.META['HTTP_AUTHORIZATION'].split()
    if len(auth) == 2:
      if auth[0].lower() == "basic":
        uname, passwd = base64.b64decode(auth[1]).decode('utf-8').split(':', 1)
        if uname in valid_api_users:
          authenticated = 1

  # Abort if API username is invalid
  if authenticated == 0:
    return outputJSON(errorMessage("401", "Unauthorized"))

  # We need at least two parameters
  param = action.split("/")
  if len(param) > 2 or (param[0] == "course" and len(param) > 1): 
    return outputJSON(errorMessage("400", "Invalid Action"))

  if len(param) < 2:
    param.append("")
	

  if param[0] == "":
    # List public courses if no action is specified
    output = get_keepcourses()
  else:
    output = get_enrolments(param[0], param[1])

  return outputJSON(output)


def get_enrolments(type, value=""):
  # Define basic clauses for the SQL statement
  select_clause = ""
  from_clause = """
    student_courseenrollment AS e
    JOIN auth_user AS u
      ON e.user_id = u.id
    JOIN external_auth_externalauthmap AS xa
      ON u.id = xa.user_id
    JOIN course_overviews_courseoverview AS c
      ON e.course_id = c.id
    LEFT JOIN student_courseaccessrole AS ar
      ON e.course_id = ar.course_id
      AND e.user_id = ar.user_id
    """
  # (NOTE: Hidden courses, such as those under evaluation, should have their visibilities set to "none".
  #        These courses should be treated same as "Hide" courses under Moodle.)
  where_clause = "e.is_active = 1 AND c.catalog_visibility != \"none\""
  order_clause = ""

  if type == "user":
    # Courses that a specific user has enrolled to.
    # Abort if keep ID does not match the UUID pattern.
    uuid_re = re.compile(r"^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$")
    if uuid_re.match(value) is None:
      return errorMessage("400", "Invalid KEEP ID")

    select_clause = """
      c.id AS course_id,
      c.display_name AS course_name,
      (case c.catalog_visibility WHEN 'none' THEN 'hide' WHEN 'both' THEN 'public' WHEN 'about' THEN 'private' END) AS visibility,
      (CASE
        WHEN u.is_superuser = 1 THEN "superuser"
        WHEN ar.role IS NOT NULL THEN ar.role
        ELSE "student"
      END) AS role_name
      """
    where_clause = "e.is_active = 1" # add
    where_clause += " AND xa.external_id = \"" + value + "\""
    order_clause = "c.id"

  elif type == "invite":
    # Courses that a specific user has been invited to enrol.
    # Abort if email address is not provided.
    email_re = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)")
    if email_re.match(value) is None:
      return errorMessage("400", "Invalid Email Address")

    select_clause = "ea.course_id AS course_id"
    from_clause = """
      student_courseenrollmentallowed AS ea
      JOIN auth_user AS u
        ON ea.email = u.email
      LEFT JOIN student_courseenrollment AS e
        ON ea.course_id = e.course_id
        AND u.id = e.user_id
      """
    where_clause = "(e.id IS NULL OR e.is_active = 0)"
    where_clause += " and ea.email = \"" + value + "\""
    order_clause = "ea.course_id"

  elif type == "enrol":
    select_clause = """
      xa.external_id AS keep_id,
      u.email AS keep_login,
      (CASE
        WHEN u.is_superuser = 1 THEN "superuser"
        WHEN ar.role IS NOT NULL THEN ar.role
        ELSE "student"
      END) AS role_name
      """
    order_clause = "c.id, u.email"

    # Complete enrolment table
    if value == "":
      select_clause = "c.id AS course_id, c.display_name AS course_name," + select_clause

    # Enrolment table for specific course
    else:
      where_clause += " AND c.id = \"" + value + "\""

  elif type == "course":
    # Course information with number of enrolled students
    select_clause = """
      c.id AS course_id,
      c.display_name AS course_name,
      CAST(DATE(c.start) AS CHAR) AS start_date,
      CAST(DATE(c.end) AS CHAR) AS end_date,
      CAST(SUM(IF(u.is_superuser != 1 AND ar.role IS NULL,1,0)) AS CHAR) AS no_of_students
      """
    where_clause += " GROUP BY c.id"
    order_clause = "c.id"

  elif type == "metric":
    if value == "course":
      # Number of Moodle courses that have students enrolled
      select_clause = "DISTINCT c.id AS course_id, c.display_name AS course_name"
      order_clause  = "c.id"

    elif value == "user":
      # Number of distinct students that enrolled into Moodle courses
      select_clause = "DISTINCT xa.external_id AS keep_id"
      order_clause  = "xa.external_id"

    else:
      return errorMessage("400", "Invalid Metric Type")

    # (NOTE: For metrics, teachers are not counted)
    where_clause += " AND u.is_superuser != 1 AND ar.role IS NULL"

  else:
    return errorMessage("400", "Invalid Action")

  query = "SELECT " + select_clause + " FROM " + from_clause + " WHERE " + where_clause + " ORDER BY " + order_clause

  conn = MySQLdb.connect("10.11.51.16","edxapp001","password","edxapp")
  cursor = conn.cursor(MySQLdb.cursors.DictCursor)
  cursor.execute(query)
  results = list(cursor) # to array

  cursor.close()
  conn.close()

  if not results:
    # Do not return empty array; Return error message instead
    return errorMessage("404", "Not Found")

  else:
    # Return result array as-is
    return results


def get_keepcourses():

  mongoClient = MongoClient(host="10.11.51.17")
  mongoDB = mongoClient.edxapp
  courses = mongoDB.modulestore.active_versions.find()

  results = []

  for course in courses:
    # content library does not have published-branch and should be skipped
    if not course['versions'].has_key('published-branch'):
      continue

    temp = {}
    search = {}

    # course org name keep_course_link display_name start course_image keep_course_image ispublic
    temp['org'] = course['org']
    temp['course'] = course['course']
    temp['name'] = course['run']
	
    # TODO: Change the below link in production deployment
    temp['keep_course_link'] = 'https://ficusedx.keep.edu.hk/courses/course-v1:' + temp['org'] + '+' + temp['course'] + '+' + temp['name'] + '/about'
    temp['ispublic'] = True

    # Institution Info
    r = requests.get('https://course.keep.edu.hk/api/new_submitted_course?id=course-v1%3A'+ temp['org'] + '%2B' + temp['course'] + '%2B' + temp['name'], auth=('M>hX3Gdr/m9<rYPyWkTaTekLpe\PgB', ''))

    if r.status_code == 200:
      info_result = r.json()

      if 'result' in info_result:
        # General case
        temp['institution_name'] = info_result['result']['institution_name']
        temp['institution_enrol'] = info_result['result']['institution_enrol']
      elif 'error' in info_result:
        # Error, course not found
        temp['institution_name'] = None
        temp['institution_enrol'] = None
      else:
        # Access denied
        temp['institution_name'] = None
        temp['institution_enrol'] = None
    else:
      temp['institution_name'] = None
      temp['institution_enrol'] = None

    # structure
    search['_id'] = course['versions']['published-branch']
    structures = mongoDB.modulestore.structures.find(search, {"blocks":1})
    for block in structures[0]['blocks']:
      if block['block_type'] == 'course' and block['block_id'] == 'course':
        # course display name
        temp['display_name'] = block['fields']['display_name']
        # course start date
        temp['start'] = str(block['fields']['start'])
        # course end date
        temp['end'] = str('2030-01-01 00:00:00')
        # course id
        temp['course_id'] = 'course-v1:' + temp['org'] + '+' + temp['course'] + '+' + temp['name']
        # course image
        if block['fields'].has_key('course_image'):
          temp['course_image'] = block['fields']['course_image']
          # TODO: Change the below link in production deployment
          temp['keep_course_image'] = 'https://ficusedx.keep.edu.hk/asset-v1:' + temp['org'] + '+' + temp['course'] + '+' + temp['name'] + '+type@asset+block@' + block['fields']['course_image']
        else:
          # TODO: Change the below link in production deployment
          temp['keep_course_image'] = 'https://ficusedx.keep.edu.hk/asset-v1:edX+DemoX+Demo_Course+type@asset+block@images_course_image.jpg'
        # whether the course should be listed on KEEPCourse page
        # (NOTE: boolean value ['fields']['xml_attributes']['ispublic'] is deprecated)
        if block['fields'].has_key('catalog_visibility'):
          if block['fields']['catalog_visibility'] == 'about' or block['fields']['catalog_visibility'] == 'none':
             temp['ispublic'] = False;

      # course overview
      elif block['block_type'] == 'about' and block['block_id'] == 'overview':
        search['_id'] = block['definition']
        overview = mongoDB.modulestore.definitions.find(search, {"fields":1})
        temp['overview'] = overview[0]['fields']['data']

      # course short description
      elif block['block_type'] == 'about' and block['block_id'] == 'short_description':
        search['_id'] = block['definition']
        overview = mongoDB.modulestore.definitions.find(search, {"fields":1})
        temp['short_description'] = overview[0]['fields']['data']

    results.append(temp)

  if not results:
    # Do not return empty array; Return error message instead
    return errorMessage("404", "Not Found")

  else:
    return results


def outputJSON(data):
  if (isinstance(data, dict)) and ("error" in data):
    # Dictionary object with the "error" key; Display the error message
    output = json.dumps(data, sort_keys=True)
    return HttpResponse(output, content_type="application/json; charset=utf-8", status=data["error"]["code"], reason=data["error"]["message"])

  elif isinstance(data, list):
    # Array object; convert all sub-elements into JSON and include element count
    results = []
    for item in data:
      results.append(json.dumps(item, sort_keys=True))
    output = '{"total_results":"' + str(len(results)) + '","results":[' + ','.join(results) + ']}'
    return HttpResponse(output, content_type="application/json; charset=utf-8")


def errorMessage(code, message):
  return {"error" : {"code" : code, "message" : message}}
