import { useMutation } from '@tanstack/react-query';
import axios from '../lib/axios';
import { useAuth } from '../contexts/AuthContext';

interface LoginCredentials {
  email: string;
  password: string;
}

interface RegisterCredentials {
  email: string;
  password: string;
}

interface AuthResponse {
  access_token: string;
  token_type: string;
}

const login = async (credentials: LoginCredentials): Promise<AuthResponse> => {
  const formData = new FormData();
  formData.append('username', credentials.email);
  formData.append('password', credentials.password);
  
  const { data } = await axios.post<AuthResponse>('/token', formData);
  return data;
};

const register = async (credentials: RegisterCredentials): Promise<AuthResponse> => {
  const { data } = await axios.post<AuthResponse>('/register', credentials);
  return data;
};

export const useLogin = () => {
  const { setToken } = useAuth();
  
  return useMutation({
    mutationFn: login,
    onSuccess: (data) => {
      setToken(data.access_token);
    },
  });
};

export const useRegister = () => {
  const { setToken } = useAuth();
  
  return useMutation({
    mutationFn: register,
    onSuccess: (data) => {
      setToken(data.access_token);
    },
  });
}; 