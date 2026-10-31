from rest_framework.routers import SimpleRouter

from .views import (CarMakeViewSet, CarModelViewSet, CarViewSet,
                    ServiceLogViewSet)

router = SimpleRouter()
router.register("makes", CarMakeViewSet, basename="carmake")
router.register("models", CarModelViewSet, basename="carmodel")
router.register("cars", CarViewSet, basename="car")
router.register("service-logs", ServiceLogViewSet, basename="servicelog")

urlpatterns = router.urls
