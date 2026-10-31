from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("categories", views.SymptomCategoryViewSet, basename="category")
router.register("symptoms", views.SymptomViewSet, basename="symptom")
router.register("causes", views.CauseViewSet, basename="cause")
router.register("links", views.CauseSymptomLinkViewSet, basename="link")
router.register("questions", views.QuestionViewSet, basename="question")
router.register("options", views.AnswerOptionViewSet, basename="option")
router.register("self-checks", views.SelfCheckViewSet, basename="selfcheck")
router.register("repair-costs", views.RepairCostViewSet, basename="repaircost")
router.register("warning-lights", views.WarningLightViewSet, basename="warninglight")
router.register("obd-codes", views.ObdCodeViewSet, basename="obdcode")
router.register("reviews", views.ContentReviewViewSet, basename="contentreview")

urlpatterns = [
    path("import/", views.ImportFlowView.as_view(), name="import-flow"),
] + router.urls
