import { lazy, Suspense } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import './index.css'
import { useAuth, homeFor } from "./auth.jsx";
import Layout from "./components/Layout.jsx";
import { Spinner } from "./components/ui.jsx";
import DiagnosisChat from "./pages/DiagnosisChat.jsx";
import Garage from "./pages/Garage.jsx";
import History from "./pages/History.jsx";
import Home from "./pages/Home.jsx";
import WarningLights from "./pages/WarningLights.jsx";
import ObdLookup from "./pages/ObdLookup.jsx";
import Login from "./pages/Login.jsx";
import Mechanics from "./pages/Mechanics.jsx";
import NewDiagnosis from "./pages/NewDiagnosis.jsx";
import Register from "./pages/Register.jsx";
import Result from "./pages/Result.jsx";
import ScamShield from "./pages/ScamShield.jsx";
import StopDriving from "./components/StopDriving.jsx";
import MechanicDashboard from "./pages/mechanic/MechanicDashboard.jsx";
import MechanicWizard from "./pages/mechanic/MechanicWizard.jsx";
import MechanicSimulator from "./pages/mechanic/MechanicSimulator.jsx";
import MechanicAiDrafts from "./pages/mechanic/MechanicAiDrafts.jsx";
import MechanicRecords from "./pages/mechanic/MechanicRecords.jsx";
import ReviewDetail, { LaunchGate, ReviewQueue } from "./pages/Review.jsx";
import Outcome from "./pages/Outcome.jsx";
import MechanicRegisterProblem from "./pages/mechanic/MechanicRegisterProblem.jsx";

const AnalyticsDashboard = lazy(() => import("./pages/AnalyticsDashboard.jsx"));

function RequireAuth() {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  return (
    <Layout>
      <Outlet />
    </Layout>
  );
}

function RequireMechanic() {
  const { user, loading } = useAuth();

  if (loading) return <Spinner />;

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (user.role !== "mechanic") {
    return <Navigate to="/" replace />;
  }

  return (
    <Layout>
      <Outlet />
    </Layout>
  );
}

function RequireReviewer() {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  if (!["reviewer", "admin"].includes(user.role)) return <Navigate to={homeFor(user)} replace />;
  return <Layout><Outlet /></Layout>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<Home />} />
        <Route path="/garage" element={<Garage />} />
        <Route path="/diagnose" element={<NewDiagnosis />} />
        <Route path="/diagnose/:id" element={<DiagnosisChat />} />
        <Route path="/result/:id" element={<Result />} />
        <Route path="/stop-driving" element={<StopDriving />} />
        <Route path="/history" element={<History />} />
        <Route path="/outcome/:sessionId" element={<Outcome />} />
        <Route path="/quote-check" element={<ScamShield />} />
        <Route path="/scam-shield" element={<ScamShield />} />
        <Route path="/mechanics" element={<Mechanics />} />
        <Route path="/lights" element={<WarningLights />} />
        <Route path="/warning-lights" element={<WarningLights />} />
        <Route path="/obd" element={<ObdLookup />} />
      </Route>
      <Route element={<RequireMechanic />}>
        <Route path="/mechanic" element={<MechanicDashboard />} />
        <Route path="/mechanic/records" element={<MechanicRecords />} />
        <Route path="/mechanic/record/new" element={<MechanicRegisterProblem />} />
        <Route path="/mechanic/records/:id" element={<MechanicRecords />} />
        <Route path="/mechanic/wizard" element={<MechanicWizard />} />
        <Route path="/mechanic/simulator" element={<MechanicSimulator />} />
        <Route path="/mechanic/ai-drafts" element={<MechanicAiDrafts />} />
      </Route>
      <Route element={<RequireReviewer />}>
        <Route path="/admin/analytics" element={<Suspense fallback={<Spinner />}><AnalyticsDashboard /></Suspense>} />
        <Route path="/review" element={<ReviewQueue />} />
        <Route path="/review/launch-gate" element={<LaunchGate />} />
        <Route path="/review/items/:type/:id" element={<ReviewDetail />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
