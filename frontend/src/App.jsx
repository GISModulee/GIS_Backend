// src/App.jsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useSelector } from "react-redux";
import { useEffect } from "react";
import LoginPage from "./components/loginPage/LoginPage.jsx";
import ForgotPassword from "./components/forgotPassword/ForgotPassword.jsx";
import Dashboard from "./components/dashboard/Dashboard";
import MapWorkspace from "./components/mapWorkspace/MapWorkspace";
import { Toaster } from "react-hot-toast";

function ProtectedRoute({ children }) {
  const isAuthenticated = useSelector((state) => state.auth?.isAuthenticated);
  const token = localStorage.getItem("token");
  if (!isAuthenticated || !token) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  useEffect(() => {
    const handlePageShow = (event) => {
      if (event.persisted || (window.performance && window.performance.navigation.type === 2)) {
        if (!localStorage.getItem("token")) {
          window.location.reload();
        }
      }
    };
    window.addEventListener("pageshow", handlePageShow);
    return () => {
      window.removeEventListener("pageshow", handlePageShow);
    };
  }, []);

  return (
    <>
      <Toaster
        position="top-center"
        toastOptions={{
          style: {
            marginTop: '1rem',
            padding: '0.5rem 1rem',
            border: '1px solid #e5e7eb',
            borderRadius: '0.5rem',
            boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
            color: '#374151',
            background: '#ffffff',
            fontSize: '0.875rem',
            fontWeight: '500',
          },
        }}
      />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />

          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/map/:caseId"
            element={
              <ProtectedRoute>
                <MapWorkspace />
              </ProtectedRoute>
            }
          />
          <Route
            path="/map"
            element={
              <ProtectedRoute>
                <MapWorkspace />
              </ProtectedRoute>
            }
          />

          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </>
  );
}