// frontend/src/context/AuthContext.jsx
// Manages authentication state backed by real server session HttpOnly cookie.

import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { getAuthStatus, loginUser, logoutUser, registerUser } from "../api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const checkStatus = useCallback(async () => {
    try {
      const res = await getAuthStatus();
      if (res && res.authenticated && res.user) {
        setUser(res.user);
      } else {
        setUser(null);
      }
    } catch (err) {
      console.error("Failed to check auth status:", err);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkStatus();
  }, [checkStatus]);

  const login = async (email, password) => {
    setError(null);
    const res = await loginUser({ email, password });
    if (res.error) {
      setError(res.error);
      return { success: false, error: res.error };
    }
    setUser(res.user);
    return { success: true, user: res.user };
  };

  const register = async (email, password, displayName) => {
    setError(null);
    const res = await registerUser({
      email,
      password,
      display_name: displayName,
    });
    if (res.error) {
      setError(res.error);
      return { success: false, error: res.error };
    }
    setUser(res.user);
    return { success: true, user: res.user };
  };

  const logout = async () => {
    try {
      await logoutUser();
    } catch (err) {
      console.error("Logout request failed:", err);
    }
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        error,
        login,
        register,
        logout,
        refreshUser: checkStatus,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
