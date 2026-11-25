from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("bonuses", views.BonusViewSet, basename="bonuses")
router.register("discipline", views.DisciplineViewSet, basename="discipline")
urlpatterns = router.urls
