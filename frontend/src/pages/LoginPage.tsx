import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useLogin } from "../api/useAuth";
import { useAuth } from "../contexts/AuthContext";
import { LoginForm } from "@/components/login-form";

export const LoginPage = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const { mutate: login, isPending: isLoading } = useLogin();

  useEffect(() => {
    if (isAuthenticated) {
      navigate("/home");
    }
  }, [isAuthenticated, navigate]);

  if (isAuthenticated) {
    return null;
  }

  const handleSubmit = ({
    email,
    password,
  }: {
    email: string;
    password: string;
  }) => {
    login(
      { email, password },
      {
        onSuccess: () => {
          navigate("/home");
        },
      }
    );
  };

  return <LoginForm onLogin={handleSubmit} loading={isLoading} />;
};
