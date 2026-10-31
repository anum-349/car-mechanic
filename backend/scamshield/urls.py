from rest_framework.routers import SimpleRouter

from .views import ScamCheckViewSet

router = SimpleRouter()
router.register("", ScamCheckViewSet, basename="scam-check")
router.register("checks", ScamCheckViewSet, basename="scamcheck")

urlpatterns = router.urls
