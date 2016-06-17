# -*- coding: utf-8 -*-
# Copyright 2016 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import os
import inspect
from unittest.case import TestCase
from buildbot_utils.test_odoo_server import has_test_errors

DBNAME = 'db-test'


class TestHasTestErrors(TestCase):

    def setUp(self):
        self.ressources_path = os.path.dirname(
            inspect.getabsfile(TestHasTestErrors))
        self.ressources_path = os.path.join(self.ressources_path, 'ressources')
        super(TestHasTestErrors, self).setUp()

    def test_has_missing_access_errors(self):
        """
        Check a list of log lines for test errors.
        Extension point to detect false positives.
        """
        fname = os.path.join(self.ressources_path, 'no_access_rule_log.txt')
        errors = has_test_errors(fname, DBNAME, check_loaded=True)
        self.assertEquals(
            6, errors, "%s should contains 6 errors for missing access "
            "rules (%d found)" % (fname, errors))

    def test_not_loaded_errors(self):
        """
        Check a list of log lines for test errors.
        Extension point to detect false positives.
        """
        fname = os.path.join(self.ressources_path, 'not_loaded_log.txt')
        errors = has_test_errors(fname, DBNAME, check_loaded=True)
        self.assertEquals(
            1, errors, "%s should contains 1 error for missing module loaded "
            "directive (%d found)" % (fname, errors))
