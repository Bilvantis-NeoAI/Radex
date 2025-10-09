'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { User, AuthContextType } from '@/types/auth';
import apiClient from '@/lib/api';

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const initializeAuth = async () => {
      try {
        const savedToken = localStorage.getItem('auth_token');
        if (savedToken) {
          setTokenState(savedToken);
          const userData = await apiClient.getCurrentUser();
          setUser(userData);
        }
      } catch (error) {
        console.error('Failed to initialize auth:', error);
        localStorage.removeItem('auth_token');
        apiClient.setToken(null);
      } finally {
        setIsLoading(false);
      }
    };

    initializeAuth();
  }, []);

  const login = async (username: string, password: string) => {
    try {
      const response = await apiClient.login(username, password);
      const { access_token, user: userData } = response;
      localStorage.setItem('loginType', 'radex');
      setTokenState(access_token);
      setUser(userData);
      apiClient.setToken(access_token);
    } catch (error) {
      throw error;
    }
  };

  const oktaLogin = async (firebaseResult: any) => {
    const tokenResp = await apiClient.syncFirebaseUser(firebaseResult);
    const access_token: string = typeof tokenResp === 'string' ? tokenResp : tokenResp.access_token;
    console.log("Setting access token from okta login");
    // console.log('Setting token:', access_token);
    localStorage.setItem('loginType', 'okta');
    const oktaUser: User = await apiClient.getCurrentUser(); // now backend receives correct token
    setTokenState(access_token);
    setUser(oktaUser);
    localStorage.setItem('auth_token', access_token);
    
  };

  const register = async (email: string, username: string, password: string) => {
    try {
      const response = await apiClient.register({ email, username, password });
      const { access_token, user: userData } = response;
      
      setTokenState(access_token);
      setUser(userData);
      apiClient.setToken(access_token);
    } catch (error) {
      throw error;
    }
  };

  const logout = () => {
    setUser(null);
    setTokenState(null);
    localStorage.removeItem('auth_token');
    localStorage.removeItem('loginType');
    apiClient.setToken(null);
    if (typeof window !== 'undefined') {
      window.location.href = '/login';
    }
  };

  const value: AuthContextType = {
    user,
    token,
    login,
    oktaLogin,
    register,
    logout,
    isAuthenticated: !!user,
    isLoading,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}