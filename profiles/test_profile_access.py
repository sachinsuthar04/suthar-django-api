from django.test import TestCase

from members.testing import api, make_admin, make_family_with_head, make_member


class ProfileReadAccess(TestCase):
    def setUp(self):
        self.family, self.head = make_family_with_head()
        self.me = make_member("Me", login=True, family=self.family)
        self.sibling = make_member("Sib", login=True, family=self.family)
        self.stranger = make_member("Stranger", login=True)

    def get(self, viewer, target):
        return api(viewer).get(f"/api/profiles/profile/{target.user.id}/")

    def test_own_profile(self):
        self.assertEqual(self.get(self.me.user, self.me).status_code, 200)

    def test_same_household_can_read(self):
        self.assertEqual(self.get(self.me.user, self.sibling).status_code, 200)

    def test_stranger_cannot_read(self):
        self.assertEqual(self.get(self.me.user, self.stranger).status_code, 403)

    def test_admin_can_read_anyone(self):
        self.assertEqual(self.get(make_admin(), self.stranger).status_code, 200)

    def test_unknown_user_404_and_anonymous_401(self):
        self.assertEqual(api(self.me.user).get("/api/profiles/profile/99999/").status_code, 404)
        self.assertEqual(api().get(f"/api/profiles/profile/{self.me.user.id}/").status_code, 401)


class ImageUpload(TestCase):
    def test_upload_works_for_a_user_without_profile_rows_yet(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from members.testing import make_user
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (4, 4)).save(buf, "PNG")
        r = api(make_user()).post("/api/profiles/profile/upload-image/",
                                  {"file": SimpleUploadedFile("a.png", buf.getvalue(), "image/png")}, format="multipart")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn("profileImageUrl", r.data)

    def test_missing_file_is_400(self):
        from members.testing import make_user
        self.assertEqual(api(make_user()).post("/api/profiles/profile/upload-image/", {}, format="multipart").status_code, 400)
