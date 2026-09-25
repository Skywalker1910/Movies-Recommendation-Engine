import hashlib
import urllib.parse
import unittest
from datetime import timedelta
from unittest.mock import patch

from app import create_app
from app.admin_service import ensure_default_model_config
from app.extensions import bcrypt, db
from app.models import AdminAccount, AdminPasswordResetToken, utc_now


class AdminRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.app.config.update({
            "ADMIN_JWT_SECRET_KEY": "separate-admin-test-secret-at-least-32-bytes",
        })

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()

    def setUp(self):
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            ensure_default_model_config()
            db.session.add(AdminAccount(
                email="admin@example.com",
                display_name="System Administrator",
                password_hash=bcrypt.generate_password_hash(
                    "Admin-Password-123!"
                ).decode("utf-8"),
            ))
            db.session.commit()
        self.client = self.app.test_client()

    def register(self, email="viewer@example.com", first_name="Viewer"):
        response = self.client.post("/auth/register", json={
            "firstName": first_name,
            "lastName": "User",
            "email": email,
            "password": "Password123!",
            "favoriteGenres": ["Drama"],
            "favoriteMovies": [550],
        })
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    def admin_login(self):
        response = self.client.post("/admin/auth/login", json={
            "email": "admin@example.com",
            "password": "Admin-Password-123!",
        })
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    @staticmethod
    def headers(token):
        return {"Authorization": f"Bearer {token}"}

    def test_user_and_admin_security_domains_are_isolated(self):
        regular = self.register()
        admin = self.admin_login()

        admin_with_user_token = self.client.get(
            "/admin/users", headers=self.headers(regular["token"])
        )
        user_with_admin_token = self.client.get(
            "/auth/me", headers=self.headers(admin["token"])
        )
        allowed = self.client.get(
            "/admin/users", headers=self.headers(admin["token"])
        )

        self.assertEqual(admin_with_user_token.status_code, 401)
        self.assertIn(user_with_admin_token.status_code, (401, 422))
        self.assertEqual(allowed.status_code, 200)
        self.assertNotIn("isAdmin", regular["user"])

    def test_admin_can_update_user_attributes_and_audit_the_change(self):
        admin = self.admin_login()
        regular = self.register()
        response = self.client.patch(
            f"/admin/users/{regular['user']['id']}",
            headers=self.headers(admin["token"]),
            json={
                "firstName": "Updated",
                "movielensUserId": 42,
                "favoriteGenres": ["Drama", "Science Fiction"],
                "watchedMovies": [550, 11],
                "preferences": {
                    "includeWatched": True,
                    "watchingFrequency": "daily",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        user = response.get_json()
        self.assertEqual(user["firstName"], "Updated")
        self.assertEqual(user["movielensUserId"], 42)

        audit = self.client.get(
            "/admin/audit-log", headers=self.headers(admin["token"])
        ).get_json()
        self.assertEqual(audit[0]["action"], "user.updated")
        self.assertEqual(audit[0]["adminName"], "System Administrator")

    def test_user_password_reset_token_is_single_use(self):
        admin = self.admin_login()
        regular = self.register()
        response = self.client.post(
            f"/admin/users/{regular['user']['id']}/password-reset",
            headers=self.headers(admin["token"]),
        )
        self.assertEqual(response.status_code, 201)
        reset_url = response.get_json()["resetUrl"]
        token = urllib.parse.parse_qs(urllib.parse.urlparse(reset_url).query)["token"][0]

        self.assertEqual(self.client.post("/auth/reset-password", json={
            "token": token,
            "newPassword": "A-New-Password-123!",
        }).status_code, 200)
        self.assertEqual(self.client.post("/auth/reset-password", json={
            "token": token,
            "newPassword": "Another-Password-123!",
        }).status_code, 400)

    def test_admin_password_setup_is_separate_and_single_use(self):
        raw_token = "isolated-admin-setup-token"
        with self.app.app_context():
            admin = AdminAccount.query.filter_by(email="admin@example.com").one()
            admin.password_reset_required = True
            db.session.add(AdminPasswordResetToken(
                admin_id=admin.id,
                token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
                expires_at=utc_now() + timedelta(minutes=30),
            ))
            db.session.commit()

        blocked = self.client.post("/admin/auth/login", json={
            "email": "admin@example.com", "password": "Admin-Password-123!"
        })
        reset = self.client.post("/admin/auth/reset-password", json={
            "token": raw_token, "newPassword": "New-Admin-Password-456!"
        })
        reused = self.client.post("/admin/auth/reset-password", json={
            "token": raw_token, "newPassword": "Another-Admin-Password!"
        })
        login = self.client.post("/admin/auth/login", json={
            "email": "admin@example.com", "password": "New-Admin-Password-456!"
        })

        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(reset.status_code, 200)
        self.assertEqual(reused.status_code, 400)
        self.assertEqual(login.status_code, 200)

    def test_operational_health_and_model_inventory(self):
        admin = self.admin_login()
        headers = self.headers(admin["token"])
        health = self.client.get("/admin/system/health", headers=headers)
        inventory = self.client.get("/admin/models", headers=headers)
        with patch("app.movie_service.movie_service.check_tmdb", return_value={
            "healthy": True,
            "configured": True,
            "statusCode": 200,
            "latencyMs": 12.5,
            "checkedAt": 1,
            "message": "TMDB API is reachable",
        }):
            tmdb = self.client.post(
                "/admin/integrations/tmdb/check", headers=headers
            )

        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.get_json()["database"]["healthy"])
        self.assertEqual(inventory.status_code, 200)
        self.assertGreaterEqual(len(inventory.get_json()["models"]), 5)
        self.assertEqual(tmdb.status_code, 200)
        self.assertTrue(tmdb.get_json()["probe"]["healthy"])

    def test_model_configuration_is_validated_and_versioned(self):
        admin = self.admin_login()
        headers = self.headers(admin["token"])
        invalid = self.client.post(
            "/admin/model-config/versions",
            headers=headers,
            json={"config": {"minimumSimilarity": 2}},
        )
        valid = self.client.post(
            "/admin/model-config/versions",
            headers=headers,
            json={
                "config": {"genreBoost": 0.4, "minimumSimilarity": 0.2},
                "reason": "Admin test",
                "activate": True,
            },
        )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(valid.status_code, 201)
        self.assertTrue(valid.get_json()["isActive"])


if __name__ == "__main__":
    unittest.main()
