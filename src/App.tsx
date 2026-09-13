import { Routes, Route } from "react-router-dom";
import Landing from "@/routes/Landing";
import AuthPage from "@/routes/AuthPage";
import AppShell from "@/routes/AppShell";
import ProtectedRoute from "@/routes/ProtectedRoute";
import NotFound from "@/routes/NotFound";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/auth" element={<AuthPage defaultMode="signin" />} />
      <Route path="/sign-in" element={<AuthPage defaultMode="signin" />} />
      <Route path="/sign-up" element={<AuthPage defaultMode="signup" />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/app" element={<AppShell />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
