import { ResultContent } from "../pages/Result.jsx";

export default function Results({ session }) {
  return <ResultContent result={session} sessionId={session.id} />;
}
