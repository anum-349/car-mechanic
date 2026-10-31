from rest_framework.routers import SimpleRouter

from .views import DiagnosisSessionViewSet

router = SimpleRouter()
router.register("sessions", DiagnosisSessionViewSet, basename="session")

urlpatterns = router.urls
