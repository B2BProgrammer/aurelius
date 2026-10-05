import { Navigate, Route, Routes } from "react-router";

import { useAuth } from "./lib/auth";
import { Dossier } from "./pages/Dossier";
import { SignIn } from "./pages/SignIn";
import { Welcome, Workspace } from "./pages/Workspace";

export function App() {
  const { session } = useAuth();
  if (!session) {
    return (
      <Routes>
        <Route path="*" element={<SignIn />} />
      </Routes>
    );
  }
  return (
    <Routes>
      <Route element={<Workspace />}>
        <Route index element={<Welcome />} />
        <Route path="clients/:clientId" element={<Dossier />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
