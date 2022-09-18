"""User View tests."""

# run these tests like:
#
#    FLASK_ENV=production python -m unittest test_user_views.py


import os
from unittest import TestCase

from models import db, connect_db, Message, User, Follows, Likes

# BEFORE we import our app, let's set an environmental variable
# to use a different database for tests (we need to do this
# before we import our app, since that will have already
# connected to the database

os.environ['DATABASE_URL'] = "postgresql:///warbler-test"


# Now we can import app

from app import app, CURR_USER_KEY, login, logout

# Create our tables (we do this here, so we only create the tables
# once for all tests --- in each test, we'll delete the data
# and create fresh new clean test data

db.drop_all()
db.create_all()

# Don't have WTForms use CSRF at all, since it's a pain to test

app.config['WTF_CSRF_ENABLED'] = False


class UserViewTestCase(TestCase):
    """Test views for users."""

    def setUp(self):
        """Create test client, add sample data."""

        db.drop_all()
        db.create_all()

        self.client = app.test_client()

        self.testuser = User.signup(username="testuser",
                                    email="test@test.com",
                                    password="testuser",
                                    image_url=None)
        self.testuser_id = 8989
        self.testuser.id = self.testuser_id

        self.u1 = User.signup("user1", "user1@user.com", "password", None)
        self.u1_id = 123
        self.u1.id = self.u1_id
        self.u2 = User.signup("user2", "user2@user.com", "password", None)
        self.u2_id = 234
        self.u2.id = self.u2_id
        self.u3 = User.signup("user3", "user3@user.com", "password", None)
        self.u3_id = 345
        self.u3.id = self.u3_id

        db.session.commit()

    def tearDown(self):
        resp = super().tearDown()
        db.session.rollback()
        return resp

    def test_signup(self):
        """Can use add a user?"""

        # Since we need to change the session to mimic logging in,
        # we need to use the changing-session trick:

        with self.client as c:

            # Now, that session setting is saved, so we can have
            # the rest of ours test

            resp = c.post("/signup", data={"username": "testuser2", "email":"test2@test.com", "password":"testuser", "image_url":None})

            user = User.query.filter_by(username="testuser2").first()
            # Make sure it redirects
            self.assertEqual(resp.status_code, 302)
            self.assertEqual(user.username, "testuser2")
            self.assertEqual(user.email, "test2@test.com")
            self.assertEqual(user.image_url, '/static/images/default-pic.png')

    def test_login(self):
        with self.client as c:
            c.post("/signup", data={"username": "testuser3", "email":"test3@test.com", "password":"testuser", "image_url":None})
            resp = c.post('/login', data={"username": "testuser", "password": "testuser"})
            self.assertEqual(resp.status_code, 302)

    def test_logout(self):
        with self.client as c:
            resp = c.get('/logout')
            self.assertEqual(resp.status_code, 302)

    def setup_following(self):
        f1 = Follows(user_being_followed_id=self.u1_id, user_following_id=self.testuser_id)
        f2 = Follows(user_being_followed_id=self.u2_id, user_following_id=self.testuser_id)
        f3 = Follows(user_being_followed_id=self.testuser_id, user_following_id=self.u1_id)
        db.session.add_all([f1,f2,f3])
        db.session.commit()
            
    def test_is_following(self):
        self.setup_following()

        with self.client as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.testuser_id
            resp = c.get(f"/users/{self.testuser_id}/following")
            self.assertIn("@user1", str(resp.data))
            self.assertIn("@user2", str(resp.data))

    def test_is_followed(self):
        self.setup_following()

        with self.client as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.testuser_id
            resp = c.get(f"/users/{self.testuser_id}/followers")
            self.assertIn("@user1", str(resp.data))
            self.assertNotIn("@user2", str(resp.data))

    def test_unauthorized_following_page_access(self):
        self.setup_following()
        with self.client as c:

            resp = c.get(f"/users/{self.testuser_id}/following", follow_redirects=True)
            self.assertEqual(resp.status_code, 200)
            self.assertNotIn("@user1", str(resp.data))
            self.assertIn("Access unauthorized", str(resp.data))

    def test_unauthorized_followers_page_access(self):
        self.setup_following()
        with self.client as c:

            resp = c.get(f"/users/{self.testuser_id}/followers", follow_redirects=True)
            self.assertEqual(resp.status_code, 200)
            self.assertNotIn("@user1", str(resp.data))
            self.assertIn("Access unauthorized", str(resp.data))


    def setup_likes(self):
        m1 = Message(text="tweet1", user_id=self.testuser_id)
        m2 = Message(text="tweet2", user_id=self.testuser_id)
        m3 = Message(id=9876, text="tweet3", user_id=self.u1_id)
        db.session.add_all([m1, m2, m3])
        db.session.commit()

        l1 = Likes(user_id=self.testuser_id, message_id=9876)

        db.session.add(l1)
        db.session.commit()

    def test_add_or_remove_like(self):
        m = Message(id=2001, text="The earth is flat", user_id=self.u1_id)
        db.session.add(m)
        db.session.commit()

        with self.client as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.testuser_id

            resp = c.post(f"/users/add_like/{2001}", follow_redirects=True)
            self.assertEqual(resp.status_code, 200)
            likes = Likes.query.filter(Likes.message_id==2001).all()
            self.assertEqual(len(likes), 1)
            self.assertEqual(likes[0].user_id, self.testuser_id)
            resp = c.post(f"/users/add_like/{2001}", follow_redirects=True)
            self.assertEqual(resp.status_code, 200)
            likes = Likes.query.filter(Likes.message_id==2001).all()
            self.assertEqual(len(likes), 0)


    def test_unauthenticated_like(self):
        self.setup_likes()
        m = Message.query.filter(Message.text=="tweet3").one()
        self.assertIsNotNone(m)

        like_count = Likes.query.count()

        with self.client as c:
            resp = c.post(f"/users/add_like/{m.id}", follow_redirects=True)
            self.assertEqual(resp.status_code, 200)
            self.assertIn("Access unauthorized", str(resp.data))
