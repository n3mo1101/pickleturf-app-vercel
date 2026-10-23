# openplay/tests.py

from datetime import date, time, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from openplay.models import OpenPlaySession, OpenPlayParticipant
from openplay.services import (
    request_join,
    leave_session,
    approve_participant,
    reject_participant,
    add_participant_manually,
    cancel_session,
)

User = get_user_model()


class OpenPlayServiceTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            first_name='Admin',
            last_name='User',
            role='admin',
            is_staff=True,
        )
        self.user1 = User.objects.create_user(
            email='player1@test.com',
            password='testpass123',
            first_name='Player',
            last_name='One',
        )
        self.user2 = User.objects.create_user(
            email='player2@test.com',
            password='testpass123',
            first_name='Player',
            last_name='Two',
        )
        self.session = OpenPlaySession.objects.create(
            title='Morning Open Play',
            date=date.today() + timedelta(days=1),
            start_time=time(8, 0),
            end_time=time(10, 0),
            capacity=3,
            fee=100,
            created_by=self.admin,
        )

    # ── Join / Leave ──────────────────────────────────────────

    def test_user_can_request_join(self):
        participant = request_join(self.user1, self.session)
        self.assertEqual(
            participant.status, OpenPlayParticipant.Status.PENDING
        )

    def test_duplicate_join_raises_error(self):
        request_join(self.user1, self.session)
        with self.assertRaises(ValidationError):
            request_join(self.user1, self.session)

    def test_user_can_leave_pending_session(self):
        request_join(self.user1, self.session)
        leave_session(self.user1, self.session)
        p = OpenPlayParticipant.objects.get(
            session=self.session, user=self.user1
        )
        self.assertEqual(p.status, OpenPlayParticipant.Status.REMOVED)

    def test_leave_nonexistent_raises_error(self):
        with self.assertRaises(ValidationError):
            leave_session(self.user1, self.session)

    # ── Approve / Reject ──────────────────────────────────────

    def test_admin_can_approve_participant(self):
        p = request_join(self.user1, self.session)
        approve_participant(p)
        p.refresh_from_db()
        self.assertEqual(p.status, OpenPlayParticipant.Status.APPROVED)

    def test_admin_can_reject_participant(self):
        p = request_join(self.user1, self.session)
        reject_participant(p)
        p.refresh_from_db()
        self.assertEqual(p.status, OpenPlayParticipant.Status.REJECTED)

    def test_approval_updates_session_capacity(self):
        p = request_join(self.user1, self.session)
        self.assertEqual(self.session.spots_remaining, 3)
        approve_participant(p)
        self.session.refresh_from_db()
        self.assertEqual(self.session.spots_remaining, 2)

    def test_session_becomes_full_when_capacity_reached(self):
        """Session status auto-updates to FULL when spots fill up."""
        u3 = User.objects.create_user(
            email='p3@test.com', password='pass',
            first_name='P', last_name='Three'
        )
        for user in [self.user1, self.user2, u3]:
            p = request_join(user, self.session)
            approve_participant(p)

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, OpenPlaySession.Status.FULL)

    def test_approve_on_full_session_raises_error(self):
        u3 = User.objects.create_user(
            email='p3@test.com', password='pass',
            first_name='P', last_name='Three'
        )
        u4 = User.objects.create_user(
            email='p4@test.com', password='pass',
            first_name='P', last_name='Four'
        )
        for user in [self.user1, self.user2, u3]:
            p = request_join(user, self.session)
            approve_participant(p)

        extra = request_join(u4, self.session)
        with self.assertRaises(ValidationError):
            approve_participant(extra)

    # ── Manual Add ────────────────────────────────────────────

    def test_admin_can_add_walkin_by_name(self):
        p = add_participant_manually(
            admin_user=self.admin,
            session=self.session,
            participant_name='Walk In Guest',
        )
        self.assertEqual(p.status, OpenPlayParticipant.Status.APPROVED)
        self.assertEqual(p.display_name, 'Walk In Guest')
        self.assertIsNone(p.user)

    def test_manual_add_to_cancelled_session_raises_error(self):
        cancel_session(self.session)
        with self.assertRaises(ValidationError):
            add_participant_manually(
                admin_user=self.admin,
                session=self.session,
                participant_name='Test Guest',
            )

    # ── Cancel Session ────────────────────────────────────────

    def test_cancel_session_removes_approved_participants(self):
        p = request_join(self.user1, self.session)
        approve_participant(p)
        cancel_session(self.session)
        p.refresh_from_db()
        self.assertEqual(p.status, OpenPlayParticipant.Status.REMOVED)

    def test_cancelled_session_join_raises_error(self):
        cancel_session(self.session)
        with self.assertRaises(ValidationError):
            request_join(self.user1, self.session)