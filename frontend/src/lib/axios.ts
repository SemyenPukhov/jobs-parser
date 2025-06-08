import axios from "axios";

// Отладочная информация
console.log("Environment variables:", import.meta.env);
console.log("VITE_API_URL:", import.meta.env.VITE_API_URL);

const base = import.meta.env.VITE_API_URL || "http://localhost:58000";
console.log("baseURL", `${base}/api`);

const api = axios.create({
  baseURL: `${base}/api`,
});

// Добавляем перехватчик для отладки запросов
api.interceptors.request.use((request) => {
  console.log("Starting Request:", request);
  return request;
});

api.interceptors.response.use(
  (response) => {
    console.log("Response:", response);
    return response;
  },
  (error) => {
    console.error("Response Error:", error);
    return Promise.reject(error);
  }
);

export default api;
