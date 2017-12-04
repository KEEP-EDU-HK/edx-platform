"""
Management command for enrolling a user into a course via the enrollment api
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from lms.djangoapps.badges.events.course_meta import award_enrollment_badge, completion_check
from lms.djangoapps.badges.utils import badges_enabled
from badges.models import BadgeClass, CourseEventBadgesConfiguration
from certificates.models import CertificateStatuses

import logging
log = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    Issue badges to existing users
    """
    help = """
    This issues badges to all the existing users.

    example:
        manage.py ... issue_badges_to_existing_users

        This command can be run multiple times.
    """

    def handle(self, *args, **options):
        """
        Get all the users and issue badges to them
        """
        
#        try:
        if badges_enabled: 
            users = User.objects.all()            
            for user in users: 
                log.info(user)
#                user = User.objects.get(username='keep_dummy')
                award_enrollment_badge(user)
                completion_check(user)
                self.course_group_check(user)
#        except:
#            pass
            
    
    def course_group_check(cls, user):
        """
        Awards a badge if a user has completed every course in a defined set.
        """
        
        config = CourseEventBadgesConfiguration.current().course_group_settings
        awards = []
        for slug, keys in config.items():
            certs = user.generatedcertificate_set.filter(
                status__in=CertificateStatuses.PASSED_STATUSES,
                course_id__in=keys,
            )
            if len(certs) == len(keys):
                awards.append(slug)

        for slug in awards:
            badge_class = BadgeClass.get_badge_class(
                slug=slug, issuing_component='openedx__course', create=False,
            )
            if badge_class and not badge_class.get_for_user(user):
                badge_class.award(user)
