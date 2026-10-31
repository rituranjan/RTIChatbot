from django.contrib.auth import get_user_model
from django.test import TestCase

from chatbot.models import AppSetting
from chatbot.services.semantic.bootstrap_data import CANONICAL_PHYSICAL_COLUMN_COUNT, COLUMN_SPECS
from chatbot.services.semantic.import_export_service import import_rti_bootstrap
from chatbot.services.semantic.matcher_service import extract_filters
from chatbot.services.semantic.dictionary_service import load_dictionary
from chatbot.services.semantic.sql_validation_service import validate_sql

User = get_user_model()


class SemanticEngineTests(TestCase):
    def setUp(self):
        AppSetting.objects.update_or_create(pk=1, defaults={"semantic_sql_settings": {"platform_enabled": True}})
        self.user = User.objects.create_user("sem", password="sem-pass-12345")

    def test_bootstrap_covers_all_canonical_columns(self):
        result = import_rti_bootstrap(self.user, replace=True)
        self.assertEqual(result["columns"], CANONICAL_PHYSICAL_COLUMN_COUNT)
        self.assertEqual(len(COLUMN_SPECS), CANONICAL_PHYSICAL_COLUMN_COUNT)
        dictionary = load_dictionary(self.user, use_cache=False)
        self.assertEqual(len(dictionary["columns"]), CANONICAL_PHYSICAL_COLUMN_COUNT)

    def test_postal_code_mapping(self):
        import_rti_bootstrap(self.user, replace=True)
        dictionary = load_dictionary(self.user, use_cache=False)
        filters, clarifications = extract_filters(
            "Show all applicants from postal code 700053", dictionary
        )
        self.assertFalse(clarifications)
        self.assertTrue(any(f["column"].endswith("pincode") and f["value"] == "700053" for f in filters))

    def test_ambiguous_number_asks_clarification(self):
        import_rti_bootstrap(self.user, replace=True)
        dictionary = load_dictionary(self.user, use_cache=False)
        filters, clarifications = extract_filters("700053", dictionary)
        self.assertFalse(filters)
        self.assertTrue(clarifications)

    def test_validation_accepts_multiline_select(self):
        import_rti_bootstrap(self.user, replace=True)
        dictionary = load_dictionary(self.user, use_cache=False)
        sql = (
            "SELECT\n    a.pincode AS applicant_postal_code\n"
            "FROM dbowdb18a5zvzr.rti_apply_nows AS a WHERE a.pincode = %s\nLIMIT %s"
        )
        out = validate_sql(sql, dictionary)
        self.assertIn("pincode", out.lower())

    def test_validation_rejects_unknown_column(self):
        import_rti_bootstrap(self.user, replace=True)
        dictionary = load_dictionary(self.user, use_cache=False)
        bad = "SELECT a.id FROM x WHERE z.secret = 1"
        with self.assertRaises(ValueError):
            validate_sql(bad, dictionary)

    def test_tracking_number_filter(self):
        import_rti_bootstrap(self.user, replace=True)
        dictionary = load_dictionary(self.user, use_cache=False)
        filters, clarifications = extract_filters(
            "Show tracking_number EF598949952IN details", dictionary
        )
        self.assertFalse(clarifications)
        self.assertTrue(any(f["value"] == "EF598949952IN" for f in filters))

    def test_normalize_from_only_sql(self):
        from chatbot.services.semantic.sql_normalize import normalize_report_sql

        out = normalize_report_sql("FROM mydb.t AS a LEFT JOIN b ON a.id = b.id")
        self.assertTrue(out.lower().startswith("select "))

    def test_normalize_select_with_newlines(self):
        from chatbot.services.semantic.sql_normalize import normalize_report_sql

        sql = "SELECT\n  a.id,\n  a.pincode\nFROM mydb.t AS a"
        out = normalize_report_sql(sql)
        self.assertIn("FROM mydb.t", out)
        self.assertTrue(out.lower().startswith("select"))
