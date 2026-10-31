import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from diagnosis.models import (DiagnosisSession, SessionAnswer, SessionResult,
                              SessionSymptom)
from diagnosis.nlu import DEFAULT_GEMINI_CHAT_COMPLETIONS_URL, FakeLLM
from garage.models import Car, CarMake, CarModel
from knowledge.models import (AnswerEffect, AnswerOption, Cause, CauseSymptomLink,
                             ObdCode, Question, Symptom, SymptomCategory)


@override_settings(ALLOW_DRAFT_CONTENT=True)
class AdaptiveDiagnosisApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="diagnosis-user", password="test-password")
        make = CarMake.objects.create(name="Test make")
        model = CarModel.objects.create(
            car_make=make, name="Test model", year_from=2020)
        self.car = Car.objects.create(user=self.user, car_model=model, year=2021)
        self.category = SymptomCategory.objects.create(name_en="Starting")
        self.cranking = Symptom.objects.create(
            category=self.category, text_en="Slow cranking")
        self.lights = Symptom.objects.create(
            category=self.category, text_en="Dim dashboard lights")
        self.battery = Cause.objects.create(
            name="Weak battery", system="electrical")
        self.starter = Cause.objects.create(
            name="Bad starter", system="electrical")
        self.unrelated = Cause.objects.create(
            name="Unrelated cause", system="fuel")
        CauseSymptomLink.objects.create(
            cause=self.battery, symptom=self.cranking, strength="often")
        CauseSymptomLink.objects.create(
            cause=self.starter, symptom=self.cranking, strength="often")
        CauseSymptomLink.objects.create(
            cause=self.battery, symptom=self.lights, strength="often")
        CauseSymptomLink.objects.create(
            cause=self.starter, symptom=self.lights, strength="rarely")
        CauseSymptomLink.objects.create(
            cause=self.unrelated, symptom=self.cranking, strength="often")
        CauseSymptomLink.objects.create(
            cause=self.unrelated, symptom=self.lights, strength="often")
        self.question = Question.objects.create(
            symptom=self.lights, text_en="Do the dashboard lights dim?")
        self.yes = AnswerOption.objects.create(
            question=self.question, label="Yes", effect=AnswerEffect.CONFIRMS,
            implies_symptom=self.lights)
        self.no = AnswerOption.objects.create(
            question=self.question, label="No", effect=AnswerEffect.DENIES,
            implies_symptom=self.lights)
        self.unsure = AnswerOption.objects.create(
            question=self.question, label="Not sure", is_unsure=True,
            effect=AnswerEffect.UNSURE)
        self.code = ObdCode.objects.create(
            code="P0301", description="Cylinder 1 misfire", system="Engine")
        self.code.causes.add(self.battery, self.starter)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = "/api/sessions/"

    def _start_text(self):
        with patch("diagnosis.views.map_text_to_symptoms",
                   return_value=[self.cranking]):
            return self.client.post(self.url, {
                "car": self.car.pk,
                "free_text": "The engine cranks slowly.",
            }, format="json")

    def test_text_flow_requires_description_and_selects_relevant_question(self):
        empty = self.client.post(self.url, {
            "car": self.car.pk, "free_text": "   ",
        }, format="json")
        self.assertEqual(empty.status_code, 400)
        self.assertFalse(DiagnosisSession.objects.exists())

        response = self._start_text()
        self.assertEqual(response.status_code, 201, response.data)
        session = DiagnosisSession.objects.get(pk=response.data["id"])
        self.assertEqual(session.diagnosis_type, "text")
        self.assertEqual(session.free_text, "The engine cranks slowly.")
        self.assertEqual(session.category_id, self.category.pk)
        self.assertEqual(response.data["question"]["id"], self.question.pk)

    def test_text_flow_uses_default_gemini_endpoint_when_base_url_is_blank(self):
        response_body = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "symptom_ids": [self.cranking.pk],
                        "confidence": 0.95,
                    }),
                },
            }],
        }
        with patch.dict("os.environ", {
                "GEMINI_API_KEY": "test-key",
                "GEMINI_MODEL": "test-model",
                "GEMINI_BASE_URL": "",
        }), patch("diagnosis.nlu.GeminiClient._post",
                  return_value=response_body) as post:
            response = self.client.post(self.url, {
                "car": self.car.pk,
                "free_text": "The engine cranks slowly.",
            }, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["question"]["id"], self.question.pk)
        self.assertEqual(post.call_args.args[0], DEFAULT_GEMINI_CHAT_COMPLETIONS_URL)
        self.assertEqual(post.call_args.args[2]["model"], "test-model")

    def test_text_flow_starts_questions_from_clear_category_when_mapper_returns_no_ids(self):
        engine_not_start = Symptom.objects.create(
            category=self.category, text_en="Engine does not start")
        for cause in (self.battery, self.starter):
            CauseSymptomLink.objects.create(
                cause=cause, symptom=engine_not_start, strength="often")
        with patch("diagnosis.nlu.get_llm_client", return_value=FakeLLM({
                "symptom_ids": [], "confidence": 0.95,
        })):
            response = self.client.post(self.url, {
                "car": self.car.pk,
                "free_text": "The engine won't start.",
            }, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["question"]["id"], self.question.pk)
        session = DiagnosisSession.objects.get(pk=response.data["id"])
        self.assertEqual(session.category_id, self.category.pk)
        self.assertFalse(session.session_symptoms.exists())

    def test_vague_engine_description_still_requests_clarification(self):
        with patch("diagnosis.nlu.get_llm_client", return_value=FakeLLM({
                "symptom_ids": [], "confidence": 0.95,
        })):
            response = self.client.post(self.url, {
                "car": self.car.pk, "free_text": "The engine isn't working.",
            }, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["clarification_required"])

    def test_resuming_unresolved_text_session_retries_context_mapping(self):
        session = DiagnosisSession.objects.create(
            user=self.user, car=self.car, free_text="The engine cranks slowly.")
        with patch("diagnosis.views.map_text_to_symptoms",
                   return_value=[self.cranking]):
            response = self.client.get(f"{self.url}{session.pk}/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["category"], self.category.pk)
        self.assertEqual(response.data["question"]["id"], self.question.pk)
        self.assertEqual(response.data["understood_symptoms"], [{
            "id": self.cranking.pk, "text": self.cranking.text_en,
        }])
        session.refresh_from_db()
        self.assertEqual(session.category_id, self.category.pk)
        self.assertTrue(SessionSymptom.objects.filter(
            session=session, symptom=self.cranking,
            source=SessionSymptom.Source.FREE_TEXT).exists())

    def test_resuming_unresolved_text_session_uses_category_fallback(self):
        engine_not_start = Symptom.objects.create(
            category=self.category, text_en="Engine does not start")
        for cause in (self.battery, self.starter):
            CauseSymptomLink.objects.create(
                cause=cause, symptom=engine_not_start, strength="often")
        session = DiagnosisSession.objects.create(
            user=self.user, car=self.car,
            free_text="The car wont start / the engine isnt working.")
        with patch("diagnosis.nlu.get_llm_client", return_value=FakeLLM({
                "symptom_ids": [], "confidence": 0.95,
        })):
            response = self.client.get(f"{self.url}{session.pk}/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["question"]["id"], self.question.pk)
        session.refresh_from_db()
        self.assertEqual(session.category_id, self.category.pk)
        self.assertFalse(session.session_symptoms.exists())

    def test_answer_is_persisted_and_unsure_does_not_create_symptom_evidence(self):
        started = self._start_text()
        answer = self.client.post(
            f'{self.url}{started.data["id"]}/answer/',
            {"question": self.question.pk, "option": self.unsure.pk},
            format="json")
        self.assertEqual(answer.status_code, 200, answer.data)
        stored = SessionAnswer.objects.get(session_id=started.data["id"])
        self.assertEqual(stored.question_id, self.question.pk)
        self.assertEqual(stored.option_id, self.unsure.pk)
        self.assertEqual(answer.data["result"]["free_text"], "The engine cranks slowly.")
        self.assertEqual(answer.data["result"]["answers"], [{
            "question": self.question.text_en,
            "answer": self.unsure.label,
            "effect": AnswerEffect.UNSURE,
        }])
        self.assertTrue(answer.data["result"]["results"])
        for result in answer.data["result"]["results"]:
            evidenced_symptoms = [
                item["symptom"]
                for kind in ("supporting", "contradicting")
                for item in result["why"][kind]
            ]
            self.assertNotIn("Dim dashboard lights", evidenced_symptoms)
        self.assertTrue(SessionResult.objects.filter(
            session_id=started.data["id"]).exists())

    def test_answers_must_match_the_current_adaptive_question(self):
        started = self._start_text()
        other_symptom = Symptom.objects.create(
            category=self.category, text_en="Fuel smell")
        CauseSymptomLink.objects.create(
            cause=self.battery, symptom=other_symptom, strength="sometimes")
        other_question = Question.objects.create(
            symptom=other_symptom, text_en="Can you smell fuel?")
        other_option = AnswerOption.objects.create(
            question=other_question, label="Not sure", is_unsure=True,
            effect=AnswerEffect.UNSURE)
        response = self.client.post(
            f'{self.url}{started.data["id"]}/answer/',
            {"question": other_question.pk, "option": other_option.pk},
            format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SessionAnswer.objects.filter(
            session_id=started.data["id"]).exists())

    @override_settings(ENGINE_CONFIDENCE_THRESHOLD=0.99, ENGINE_MIN_GAP=0.98)
    def test_answer_changes_the_next_question_and_result_evidence(self):
        clicks = Symptom.objects.create(
            category=self.category, text_en="A clicking sound")
        CauseSymptomLink.objects.create(
            cause=self.battery, symptom=clicks, strength="rarely")
        CauseSymptomLink.objects.create(
            cause=self.starter, symptom=clicks, strength="often")
        next_question = Question.objects.create(
            symptom=clicks, text_en="Do you hear repeated clicks?")
        next_yes = AnswerOption.objects.create(
            question=next_question, label="Yes", effect=AnswerEffect.CONFIRMS,
            implies_symptom=clicks)
        AnswerOption.objects.create(
            question=next_question, label="No", effect=AnswerEffect.DENIES,
            implies_symptom=clicks)
        AnswerOption.objects.create(
            question=next_question, label="Not sure", is_unsure=True,
            effect=AnswerEffect.UNSURE)

        started = self._start_text()
        first_question_id = started.data["question"]["id"]
        first_option = self.yes if first_question_id == self.question.pk else next_yes
        expected_next_id = (next_question.pk if first_question_id == self.question.pk
                            else self.question.pk)
        answer = self.client.post(
            f'{self.url}{started.data["id"]}/answer/',
            {"question": first_question_id, "option": first_option.pk},
            format="json")
        self.assertEqual(answer.status_code, 200, answer.data)
        self.assertFalse(answer.data["done"], answer.data)
        self.assertEqual(answer.data["question"]["id"], expected_next_id)

        final_question = (next_question if expected_next_id == next_question.pk
                          else self.question)
        final_option = next_yes if final_question.pk == next_question.pk else self.yes
        finished = self.client.post(
            f'{self.url}{started.data["id"]}/answer/',
            {"question": final_question.pk, "option": final_option.pk},
            format="json")
        self.assertTrue(finished.data["done"])
        for result in finished.data["result"]["results"]:
            evidenced_symptoms = {
                item["symptom"]
                for kind in ("supporting", "contradicting")
                for item in result["why"][kind]
            }
            self.assertIn("Dim dashboard lights", evidenced_symptoms)
            self.assertIn("A clicking sound", evidenced_symptoms)

    def test_obd_flow_uses_code_causes_and_rejects_mixed_text(self):
        mixed = self.client.post(self.url, {
            "car": self.car.pk,
            "obd_code": self.code.code,
            "free_text": "The car shakes.",
        }, format="json")
        self.assertEqual(mixed.status_code, 400)
        self.assertFalse(DiagnosisSession.objects.exists())

        outside_symptom = Symptom.objects.create(
            category=self.category, text_en="Fuel smell")
        Question.objects.create(
            symptom=outside_symptom, text_en="Can you smell fuel?")
        response = self.client.post(self.url, {
            "car": self.car.pk, "obd_code": self.code.code,
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["diagnosis_type"], "obd")
        self.assertEqual(response.data["obd_context"]["code"], "P0301")
        self.assertEqual(response.data["question"]["id"], self.question.pk)
        session = DiagnosisSession.objects.get(pk=response.data["id"])
        self.assertEqual(session.obd_code_id, self.code.pk)
        self.assertEqual(session.free_text, "")
        resumed = self.client.get(f"{self.url}{session.pk}/")
        self.assertEqual(resumed.status_code, 200, resumed.data)
        self.assertEqual(resumed.data["obd_context"]["code"], self.code.code)
        self.assertEqual(resumed.data["question"]["id"], self.question.pk)
        unrelated_text = self.client.post(
            f'{self.url}{session.pk}/free-text/',
            {"text": "The engine shakes."}, format="json")
        self.assertEqual(unrelated_text.status_code, 400)

        answered = self.client.post(
            f'{self.url}{session.pk}/answer/',
            {"question": self.question.pk, "option": self.yes.pk},
            format="json")
        self.assertEqual(answered.status_code, 200, answered.data)
        self.assertTrue(answered.data["done"])
        self.assertEqual(
            answered.data["result"]["obd_context"]["code"], self.code.code)
        self.assertEqual(
            {item["cause"] for item in answered.data["result"]["results"]},
            {self.battery.pk, self.starter.pk})

    def test_ambiguous_text_can_be_clarified_without_losing_initial_context(self):
        with patch("diagnosis.views.map_text_to_symptoms", return_value=[]):
            started = self.client.post(self.url, {
                "car": self.car.pk, "free_text": "The car feels unusual.",
            }, format="json")
        self.assertEqual(started.status_code, 201)
        self.assertTrue(started.data["clarification_required"])
        session = DiagnosisSession.objects.get(pk=started.data["id"])
        self.assertIsNone(session.category_id)

        with patch("diagnosis.views.map_text_to_symptoms",
                   return_value=[self.cranking]):
            clarified = self.client.post(
                f'{self.url}{session.pk}/free-text/',
                {"text": "It cranks slowly when starting."}, format="json")
        self.assertEqual(clarified.status_code, 200, clarified.data)
        session.refresh_from_db()
        self.assertEqual(session.category_id, self.category.pk)
        self.assertIn("The car feels unusual.", session.free_text)
        self.assertIn("It cranks slowly when starting.", session.free_text)
        self.assertEqual(clarified.data["question"]["id"], self.question.pk)

    def test_obd_without_linked_diagnostic_data_returns_explicit_limitation(self):
        unsupported = ObdCode.objects.create(
            code="P0999", description="Unmapped code", system="Engine")
        response = self.client.post(self.url, {
            "car": self.car.pk, "obd_code": unsupported.code,
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["done"])
        self.assertIn("insufficient", response.data["result"]["message"])
        self.assertEqual(response.data["result"]["results"], [])
