"""NFR-6 maintainability: separate apps, each with its own tests, kept apart (SAD §4.1).

These tests read the source code rather than run it, so a change that merges two apps,
drops an app's tests or reaches into another app's internals fails CI before review.
"""

import ast
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase

BASE_DIR = Path(settings.BASE_DIR)

# The apps the SRS names. Others (such as reports, SAD §4.1) may be added.
SRS_APPS = {"accounts", "rooms", "fees", "complaints", "visitors"}

# What one app may import from another: its models, and the shared role checks.
SHARED_MODULES = {"accounts.decorators"}

TEST_CASE_BASES = {"TestCase", "TransactionTestCase", "SimpleTestCase", "LiveServerTestCase"}


def local_apps():
    """Installed apps whose code lives in this repository."""
    return {
        config.label: Path(config.path)
        for config in apps.get_app_configs()
        if Path(config.path).is_relative_to(BASE_DIR) and ".venv" not in Path(config.path).parts
    }


def python_files(app_path, include_tests=True):
    for path in app_path.rglob("*.py"):
        parts = path.relative_to(app_path).parts
        if "migrations" in parts:
            continue
        if not include_tests and (parts[0] in ("tests", "tests.py")):
            continue
        yield path


def test_modules(app_path):
    if (app_path / "tests.py").exists():
        return [app_path / "tests.py"]
    return sorted((app_path / "tests").glob("test*.py"))


def imported_modules(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module
            # "from fees import views" imports fees.views
            for alias in node.names:
                yield f"{node.module}.{alias.name}"


def read_source(path):
    # utf-8-sig also accepts files saved with a byte-order mark by Windows editors.
    return path.read_text(encoding="utf-8-sig")


def test_classes(path):
    """Yield (class name, is a test case, uses the test client) for each class in a module.

    Test classes often subclass a shared base defined in the same file, so a class whose
    name ends in "Tests" counts too.
    """
    source = read_source(path)
    for node in ast.parse(source).body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {getattr(base, "id", getattr(base, "attr", "")) for base in node.bases}
        is_test = bool(bases & TEST_CASE_BASES) or node.name.endswith("Tests")
        uses_client = "self.client" in (ast.get_source_segment(source, node) or "")
        yield node.name, is_test, uses_client


class AppStructureTests(SimpleTestCase):
    def test_code_stays_split_into_the_srs_apps(self):
        self.assertLessEqual(SRS_APPS, set(local_apps()))

    def test_every_app_has_its_own_tests(self):
        for label, path in local_apps().items():
            with self.subTest(app=label):
                modules = test_modules(path)
                self.assertTrue(modules, f"{label} has no tests.py or tests/test*.py")
                classes = [c for module in modules for c in test_classes(module) if c[1]]
                self.assertTrue(classes, f"{label} has no test case classes")

    def test_apps_with_pages_have_unit_and_integration_tests(self):
        """An app with URLs needs tests through the test client and tests without it."""
        for label, path in local_apps().items():
            if not (path / "urls.py").exists():
                continue
            with self.subTest(app=label):
                classes = [c for module in test_modules(path) for c in test_classes(module) if c[1]]
                self.assertTrue(
                    any(uses_client for _, _, uses_client in classes),
                    f"{label} has no integration tests (none use self.client)",
                )
                self.assertTrue(
                    any(not uses_client for _, _, uses_client in classes),
                    f"{label} has no unit tests (every test class uses self.client)",
                )


class AppBoundaryTests(SimpleTestCase):
    """SAD §4.1: "No app uses another app's internal helpers"."""

    def test_apps_only_use_other_apps_models_and_shared_role_checks(self):
        labels = set(local_apps())
        allowed = {f"{label}.models" for label in labels} | SHARED_MODULES
        problems = []
        for label, path in local_apps().items():
            for source in python_files(path):
                tree = ast.parse(read_source(source))
                for module in imported_modules(tree):
                    root = module.split(".")[0]
                    if root == label or root not in labels or module == root:
                        continue
                    if module in allowed or any(module.startswith(f"{a}.") for a in allowed):
                        continue
                    problems.append(f"{source.relative_to(BASE_DIR)} imports {module}")
        self.assertEqual(problems, [], "Use the other app's models, or move shared code")

    def test_the_boundary_check_catches_a_reach_in(self):
        tree = ast.parse("from fees.views import fee_list\nfrom rooms import forms\n")
        modules = set(imported_modules(tree))
        self.assertIn("fees.views", modules)
        self.assertIn("rooms.forms", modules)


class ContinuousIntegrationTests(SimpleTestCase):
    """CI runs every test on each push and pull request (NFR-6)."""

    def setUp(self):
        self.workflow = (BASE_DIR / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    def test_ci_runs_on_every_push_and_pull_request(self):
        self.assertIn("push:", self.workflow)
        self.assertIn("pull_request:", self.workflow)
        self.assertIn('branches: ["**"]', self.workflow)

    def test_ci_runs_checks_migrations_and_the_whole_suite(self):
        self.assertIn("python manage.py check", self.workflow)
        self.assertIn("python manage.py makemigrations --check --dry-run", self.workflow)
        # No app label after "test", so every app's tests run.
        self.assertIn("python manage.py test --verbosity 2\n", self.workflow)
