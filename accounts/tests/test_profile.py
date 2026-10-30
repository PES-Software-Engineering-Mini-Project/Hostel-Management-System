from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class ProfileTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.student = User.objects.create_user(
            srn="PES1UG23CS010", email="student@example.com", password="student-password",
            first_name="Student", last_name="User", contact_number="9876543210",
            branch="CSE", year_of_study=2,
        )
        self.other_student = User.objects.create_user(
            srn="PES1UG23CS011", email="other@example.com", password="other-password",
            first_name="Other", last_name="Student", contact_number="9876543211",
        )
        self.admin_user = User.objects.create_user(
            srn="PES1UG23CS012", email="admin@example.com", password="admin-password",
            first_name="Admin", last_name="User", contact_number="9876543212",
            role=User.Role.ADMIN,
        )


class StudentProfileEditTests(ProfileTestCase):
    def profile_data(self, **overrides):
        data = {
            "email": "student@example.com",
            "contact_number": "9000000001",
            "branch": "ECE",
            "year_of_study": 3,
        }
        data.update(overrides)
        return data

    def test_student_can_edit_own_contact_info(self):
        self.client.force_login(self.student)

        response = self.client.post(reverse("profile-edit"), self.profile_data(), follow=True)

        self.assertRedirects(response, reverse("profile-edit"))
        self.student.refresh_from_db()
        self.assertEqual(self.student.contact_number, "9000000001")
        self.assertEqual(self.student.branch, "ECE")
        self.assertEqual(self.student.year_of_study, 3)
        self.assertContains(response, "Your profile has been updated.")

    def test_profile_form_is_prefilled_with_current_values(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("profile-edit"))

        self.assertContains(response, 'value="student@example.com"')
        self.assertContains(response, 'value="9876543210"')
        self.assertContains(response, 'value="CSE"')

    def test_srn_and_role_cannot_change_even_with_extra_post_fields(self):
        self.client.force_login(self.student)

        self.client.post(
            reverse("profile-edit"),
            self.profile_data(srn="PES1UG99XX999", role="admin"),
        )

        self.student.refresh_from_db()
        self.assertEqual(self.student.srn, "PES1UG23CS010")
        self.assertEqual(self.student.role, get_user_model().Role.STUDENT)

    def test_admin_cannot_use_student_profile_page(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("profile-edit"))

        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_is_sent_to_login(self):
        response = self.client.get(reverse("profile-edit"))

        self.assertRedirects(response, f"{reverse('login')}?next={reverse('profile-edit')}")

    def test_duplicate_email_shows_error_next_to_field_and_keeps_values(self):
        self.client.force_login(self.student)

        response = self.client.post(
            reverse("profile-edit"), self.profile_data(email="OTHER@example.com")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email address already exists.")
        self.assertContains(response, 'value="9000000001"')
        self.student.refresh_from_db()
        self.assertEqual(self.student.contact_number, "9876543210")


class AdminStudentRecordTests(ProfileTestCase):
    def admin_data(self, **overrides):
        data = {
            "first_name": "Student",
            "last_name": "User",
            "email": "student@example.com",
            "contact_number": "9111111111",
            "branch": "ME",
            "year_of_study": 4,
        }
        data.update(overrides)
        return data

    def test_admin_can_view_student_list(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("student-list"))

        self.assertContains(response, "PES1UG23CS010")
        self.assertContains(response, "PES1UG23CS011")
        self.assertNotContains(response, "PES1UG23CS012")  # admins are not students

    def test_admin_can_edit_any_student_record(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("student-edit", args=[self.student.pk]), self.admin_data(), follow=True
        )

        self.assertRedirects(response, reverse("student-list"))
        self.student.refresh_from_db()
        self.assertEqual(self.student.contact_number, "9111111111")
        self.assertEqual(self.student.branch, "ME")
        self.assertEqual(self.student.year_of_study, 4)

    def test_admin_edit_cannot_change_srn_or_role_with_extra_post_fields(self):
        self.client.force_login(self.admin_user)

        self.client.post(
            reverse("student-edit", args=[self.student.pk]),
            self.admin_data(srn="PES1UG99XX999", role="admin"),
        )

        self.student.refresh_from_db()
        self.assertEqual(self.student.srn, "PES1UG23CS010")
        self.assertEqual(self.student.role, get_user_model().Role.STUDENT)

    def test_student_cannot_open_admin_student_pages_by_changing_url(self):
        self.client.force_login(self.other_student)

        list_response = self.client.get(reverse("student-list"))
        edit_response = self.client.get(reverse("student-edit", args=[self.student.pk]))
        post_response = self.client.post(
            reverse("student-edit", args=[self.student.pk]), self.admin_data()
        )

        self.assertEqual(list_response.status_code, 403)
        self.assertEqual(edit_response.status_code, 403)
        self.assertEqual(post_response.status_code, 403)
        self.student.refresh_from_db()
        self.assertEqual(self.student.contact_number, "9876543210")

    def test_admin_edit_of_unknown_student_is_404(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("student-edit", args=[99999]))

        self.assertEqual(response.status_code, 404)

    def test_admin_cannot_set_duplicate_email(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("student-edit", args=[self.student.pk]),
            self.admin_data(email="other@example.com"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email address already exists.")
