from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from diagnosis.models import (
    DiagnosisSession, MechanicInspection, MechanicOutcomeAudit,
    MechanicRepairOutcome, Outcome,
)
from garage.models import Car, CarMake, CarModel
from knowledge.models import Cause, SymptomCategory


class MechanicRecordsApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.mechanic = user_model.objects.create_user(
            username="mechanic-record-test", password="test-password",
            role="mechanic")
        self.owner = user_model.objects.create_user(
            username="record-owner-test", password="test-password")
        make = CarMake.objects.create(name="Records test make")
        model = CarModel.objects.create(
            car_make=make, name="Records test model", year_from=2020)
        self.mechanic_car = Car.objects.create(
            user=self.mechanic, car_model=model, year=2021)
        self.owner_car = Car.objects.create(
            user=self.owner, car_model=model, year=2021)
        self.cause = Cause.objects.create(
            name="Test battery", system="electrical")
        self.category = SymptomCategory.objects.create(name_en="Starting")
        self.client = APIClient()
        self.client.force_authenticate(self.mechanic)
        self.base_url = "/api/mechanic/records/"

    def _mechanic_session(self):
        return DiagnosisSession.objects.create(
            user=self.mechanic, car=self.mechanic_car, category=self.category,
            free_text="The engine cranks slowly.",
            mechanic_reporter=self.mechanic)

    def test_registration_uses_existing_diagnosis_start_and_is_scoped_to_garage(self):
        cars = self.client.get(f"{self.base_url}vehicles/")
        self.assertEqual(cars.status_code, 200)
        self.assertEqual([car["id"] for car in cars.data], [self.mechanic_car.pk])

        response = self.client.post("/api/sessions/", {
            "car": self.mechanic_car.pk,
            "free_text": "The engine cranks slowly.",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        session = DiagnosisSession.objects.get(pk=response.data["id"])
        self.assertEqual(session.mechanic_reporter_id, self.mechanic.pk)
        self.assertEqual(self.client.get(self.base_url).data["count"], 1)

        other_session = DiagnosisSession.objects.create(
            user=self.owner, car=self.owner_car, category=self.category,
            free_text="Customer-only session.")
        self.assertEqual(
            self.client.get(f"{self.base_url}{other_session.pk}/").status_code,
            404)

    def test_only_assigned_customer_records_are_visible(self):
        session = DiagnosisSession.objects.create(
            user=self.owner, car=self.owner_car, category=self.category,
            free_text="Owner-authorized session.",
            status=DiagnosisSession.Status.COMPLETED)
        self.assertEqual(self.client.get(self.base_url).data["count"], 0)
        owner_client = APIClient()
        owner_client.force_authenticate(self.owner)
        assigned = owner_client.post(
            f"/api/sessions/{session.pk}/outcome/", {
                "actual_cause": None,
                "actual_cause_text": "A loose battery cable.",
                "was_helpful": True,
                "mechanic": self.mechanic.pk,
                "notes": "Private owner feedback.",
            }, format="json")
        self.assertEqual(assigned.status_code, 201, assigned.data)
        response = self.client.get(f"{self.base_url}{session.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], session.pk)
        self.assertIsNone(response.data["outcome"])
        self.assertNotIn("Private owner feedback.", str(response.data))
        repair = self.client.post(f"{self.base_url}{session.pk}/outcome/", {
            "actual_cause_text": "Loose battery cable",
            "repair_status": "completed",
            "result_status": "resolved",
            "repair_actions": "Secured the cable.",
        }, format="json")
        self.assertEqual(repair.status_code, 201, repair.data)
        self.assertEqual(Outcome.objects.get(session=session).notes,
                         "Private owner feedback.")

    def test_inspection_requires_validation_and_is_immutable_after_submission(self):
        session = self._mechanic_session()
        endpoint = f"{self.base_url}{session.pk}/inspections/"
        draft = self.client.post(endpoint, {
            "findings": "Battery voltage is below specification.",
        }, format="json")
        self.assertEqual(draft.status_code, 201, draft.data)
        self.assertEqual(draft.data["status"], MechanicInspection.Status.DRAFT)

        submit_url = f'{endpoint}{draft.data["id"]}/submit/'
        invalid = self.client.post(submit_url, {}, format="json")
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("tests_performed", invalid.data)

        self.client.patch(f'{endpoint}{draft.data["id"]}/', {
            "tests_performed": "Battery load test",
        }, format="json")
        submitted = self.client.post(submit_url, {}, format="json")
        self.assertEqual(submitted.status_code, 200, submitted.data)
        self.assertEqual(submitted.data["status"], MechanicInspection.Status.SUBMITTED)
        locked = self.client.patch(f'{endpoint}{draft.data["id"]}/', {
            "findings": "Changed after submit.",
        }, format="json")
        self.assertEqual(locked.status_code, 400)

    def test_outcome_totals_audit_and_corrections_are_persisted(self):
        session = self._mechanic_session()
        endpoint = f"{self.base_url}{session.pk}/outcome/"
        draft = self.client.post(endpoint, {
            "actual_cause": self.cause.pk,
            "repair_status": "completed",
            "result_status": "resolved",
            "repair_actions": "Replaced the battery.",
            "parts_cost": 12000,
            "labor_cost": 1500,
            "other_cost": 500,
        }, format="json")
        self.assertEqual(draft.status_code, 201, draft.data)
        outcome = MechanicRepairOutcome.objects.get(session=session)
        self.assertEqual(outcome.actual_cost, 14000)
        self.assertIsNone(outcome.submitted_at)

        invalid_submit = self.client.post(f"{endpoint}submit/", {}, format="json")
        self.assertEqual(invalid_submit.status_code, 200, invalid_submit.data)
        self.assertIsNotNone(outcome.__class__.objects.get(pk=outcome.pk).submitted_at)
        self.assertEqual(MechanicOutcomeAudit.objects.filter(
            outcome=outcome).count(), 2)

        correction = self.client.patch(endpoint, {
            "repair_actions": "Replaced and tested the battery.",
        }, format="json")
        self.assertEqual(correction.status_code, 200, correction.data)
        updated = MechanicRepairOutcome.objects.get(pk=outcome.pk)
        self.assertIsNone(updated.submitted_at)
        self.assertEqual(MechanicOutcomeAudit.objects.filter(
            outcome=outcome, action="corrected").count(), 1)

    def test_non_mechanic_cannot_read_records(self):
        session = self._mechanic_session()
        self.client.force_authenticate(self.owner)
        response = self.client.get(f"{self.base_url}{session.pk}/")
        self.assertEqual(response.status_code, 403)
