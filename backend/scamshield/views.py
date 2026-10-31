from decimal import Decimal

from diagnosis.engine import rank_causes
from diagnosis.models import DiagnosisSession
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .logic import (GENERIC_PROOF_SUGGESTIONS, cost_payload, evaluate,
                    find_cost)
from .models import ScamCheck
from .serializers import ScamCheckCreateSerializer, ScamCheckSerializer


class ScamCheckViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                       mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = ScamCheck.objects.none()
    serializer_class = ScamCheckSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "scam_check"

    def get_queryset(self):
        return ScamCheck.objects.filter(user=self.request.user).select_related(
            "session", "claimed_cause").order_by("-id")

    @extend_schema(request=ScamCheckCreateSerializer,
                   responses={201: ScamCheckSerializer})
    def create(self, request, *args, **kwargs):
        incoming = ScamCheckCreateSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        values = incoming.validated_data
        session = values["session"]
        if session.user_id != request.user.pk:
            raise NotFound()
        if session.status != DiagnosisSession.Status.COMPLETED:
            raise serializers.ValidationError({
                "session": "Complete this diagnosis before checking a quote."})

        city = values.get("city") or request.user.city
        cause = values.get("claimed_cause")
        all_ranked = rank_causes(session, top=None)
        candidates = [{
            "id": item["cause"].pk,
            "name": item["cause"].name,
            "confidence": str(item["confidence"]),
        } for item in all_ranked]
        limited = cause is None
        if limited:
            plausibility = Decimal("0.50")
            verdict = ScamCheck.Verdict.DOUBTFUL
            reasons = ["Choose a cause from the diagnosis results before comparing the quote."]
            proof_suggestions = list(GENERIC_PROOF_SUGGESTIONS)
            cost, price_basis = None, "unavailable"
        else:
            plausibility, verdict, reasons, proof_suggestions = evaluate(
                session, cause, values["quoted_price"], city)
            cost, price_basis = find_cost(cause, city)

        check = ScamCheck.objects.create(
            user=request.user,
            session=session,
            claimed_cause=cause,
            claim_text=values.get("claim_text") or (cause.name if cause else ""),
            quoted_price=values["quoted_price"],
            plausibility=plausibility,
            verdict=verdict,
            city=city,
            price_basis=price_basis,
            cost=cost_payload(cost, price_basis),
            reasons=reasons,
            proof_suggestions=proof_suggestions,
            candidate_causes=candidates,
            limited=limited,
        )
        return Response(ScamCheckSerializer(check).data,
                        status=status.HTTP_201_CREATED)
